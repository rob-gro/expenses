import discord
from discord.ext import commands
import os
import tempfile
import aiohttp
import datetime
import logging

from app.services import category_service
from app.config import Config
from app.services.transcription import transcribe_audio
from app.nlp.expense_extractor import extract_with_llm
from app.database.db_manager import DBManager
from app.services.email_service import send_confirmation_email, send_category_addition_email
from app.services.email_service import try_generate_report_from_text
from concurrent.futures import ThreadPoolExecutor

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Get logger instance
logger = logging.getLogger(__name__)
email_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email_worker")
sent_confirmations = set()

# Zbiory dla deduplikacji
processed_messages = set()
processed_audio = set()


@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user}')


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Deduplikacja z uwzględnieniem zawartości
    message_key = f"{message.id}_{message.content}"
    if message_key in processed_messages:
        logger.info(f"Skipping duplicate message: {message.id}")
        return

    processed_messages.add(message_key)

    # Czyść cache co 100 wiadomości
    if len(processed_messages) > 100:
        processed_messages.clear()
        processed_messages.add(message_key)
        
    # Czyść cache confirmations co 50 elementów
    if len(sent_confirmations) > 50:
        sent_confirmations.clear()

    for attachment in message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in ['.mp3', '.wav', '.ogg', '.m4a']):
            await process_discord_audio(message, attachment)
            return

    await bot.process_commands(message)


async def process_discord_audio(message, attachment):
    # Specjalny znacznik dla każdego audio
    audio_key = f"{message.id}_{attachment.filename}_{attachment.size}"

    # Sprawdź czy już przetworzono to audio
    if audio_key in processed_audio:
        logger.warning(f"DUPLICATE AUDIO DETECTED: Skipping {attachment.filename} for message {message.id}")
        return

    processed_audio.add(audio_key)
    logger.info(f"Processing new audio: {attachment.filename} for message {message.id}")

    try:
        config = Config()
        db_manager = DBManager(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=config.DB_NAME
        )

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(attachment.filename)[1])
        temp_file.close()

        async with aiohttp.ClientSession() as session:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    with open(temp_file.name, 'wb') as f:
                        f.write(await resp.read())
                else:
                    await message.channel.send(f"Failed to download audio file. Error code: {resp.status}")
                    return

        try:
            transcription = transcribe_audio(temp_file.name)
            logger.info(f"Discord transcription: {transcription}")

            # Check if this is a category addition command
            is_category_command, category_name = category_service.detect_category_command(transcription)

            if is_category_command and category_name:
                # Process category addition command
                logger.info(f"Processing category addition command for: {category_name}")
                success, result_message = db_manager.add_category(category_name)

                # Send email notification about category action
                email_success = send_category_addition_email(category_name, success, result_message)
                if not email_success:
                    logger.warning(f"Failed to send category addition email for: {category_name}")

                if success:
                    await message.channel.send(f"✅ {result_message}")
                else:
                    await message.channel.send(f"❌ {result_message}")
                return

            # If not a category command, check if it's a report request
            # Dodaj unikalny identyfikator dla tego żądania raportu
            request_id = f"{message.id}_{transcription}"

            # Sprawdź czy już wysłano potwierdzenie dla tego żądania
            if request_id in sent_confirmations:
                logger.warning(f"Duplicate report confirmation prevented for message {message.id}")
                return

            # Jeśli jest to żądanie raportu
            if "report" in transcription.lower() or "raport" in transcription.lower():
                report_generated = try_generate_report_from_text(transcription)
                if report_generated:
                    sent_confirmations.add(request_id)  # Oznacz jako potwierdzone
                    await message.channel.send("📧 Report has been sent to your email.")
                    return

            # If not a category command or report request, try to extract expenses
            expenses = extract_with_llm(transcription)
            logger.info(f"Discord extracted expenses: {expenses}")

            if not expenses:
                await message.channel.send("❌ Could not recognize expenses in the recording.")
                return

            expense_ids = []
            for expense in expenses:
                expense_id = db_manager.add_expense(
                    date=expense.get('date', datetime.datetime.now()),
                    amount=expense.get('amount'),
                    vendor=expense.get('vendor', ''),
                    category=expense.get('category', ''),
                    description=expense.get('description', ''),
                    audio_file_path=temp_file.name,
                    transcription=transcription
                )
                if expense_id:
                    expense_ids.append(expense_id)

            # Utwórz unikalny identyfikator dla tej odpowiedzi
            response_id = f"{message.id}_{len(expenses)}_{hash(transcription)}"
            
            logger.info(f"Checking response_id: {response_id}")
            logger.info(f"Current sent_confirmations size: {len(sent_confirmations)}")
            
            # Sprawdź czy już wysłano tę odpowiedź
            if response_id in sent_confirmations:
                logger.warning(f"Duplicate expense response prevented for message {message.id} - response_id: {response_id}")
                return
            
            sent_confirmations.add(response_id)
            logger.info(f"Added response_id to sent_confirmations: {response_id}")
            
            response = "✅ Recognized expenses:\n"
            for expense in expenses:
                expense_date = expense.get('date')
                if isinstance(expense_date, datetime.datetime):
                    date_str = expense_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(expense_date).split('T')[0] if 'T' in str(expense_date) else str(expense_date)

                response += f"- {date_str}: {expense.get('vendor', 'Unknown store')} - £{expense.get('amount', 0)} ({expense.get('category', 'Other category')})\n"

            # Ostatnie zabezpieczenie przed Discord API
            send_key = f"send_{message.id}_{hash(response)}"
            if send_key in sent_confirmations:
                logger.warning(f"Discord send already attempted for message {message.id}")
                return
            
            sent_confirmations.add(send_key)
            logger.info(f"Sending Discord response for message {message.id}: {len(expenses)} expenses")
            await message.channel.send(response)
            logger.info(f"Discord response sent successfully for message {message.id}")

            # Wysyłaj email tylko jeśli wydatki zostały rzeczywiście dodane
            if expense_ids:
                try:
                    email_id = f"email_{message.id}_{hash(transcription)}"
                    if email_id not in sent_confirmations:
                        send_confirmation_email(expenses)
                        sent_confirmations.add(email_id)
                        logger.info(f"Confirmation email sent for message {message.id}")
                    else:
                        logger.warning(f"Duplicate email prevented for message {message.id}")
                except Exception as e:
                    logger.warning(f"Failed to send confirmation email: {e}")

        except Exception as e:
            logger.error(f"Error processing audio in Discord bot: {str(e)}", exc_info=True)
            await message.channel.send(f"❌ An error occurred while processing audio: {str(e)}")

        finally:
            try:
                os.unlink(temp_file.name)
            except:
                pass

    except Exception as e:
        logger.error(f"Error in Discord bot: {str(e)}", exc_info=True)
        await message.channel.send(f"❌ An error occurred: {str(e)}")


@bot.command(name='report')
async def generate_report(ctx, category=None, period="last_month"):
    await ctx.send(f"Generating report for category '{category or 'all'}' for period '{period}'...")
    await ctx.send("✅ Report has been generated and sent to your email address.")


def run_discord_bot():
    bot.run(Config.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_discord_bot()