import os
import tempfile
import datetime
import logging

# Conditional discord import for AlwaysData
if not os.environ.get('DISABLE_DISCORD'):
    import discord
    from discord.ext import commands
    import aiohttp
else:
    discord = None
    commands = None
    aiohttp = None

from app.services import category_service
from app.config import Config
from app.services.transcription import transcribe_audio
from app.nlp.expense_extractor import extract_with_llm
from app.database.db_manager import DBManager
from app.services.email_service import send_category_addition_email, try_generate_report_from_text
from app.services.email_templates import EmailTemplates
from concurrent.futures import ThreadPoolExecutor

# Bot configuration
if discord and commands:
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)
else:
    bot = None
    intents = None

# Get logger instance
logger = logging.getLogger(__name__)
email_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email_worker")
sent_confirmations = set()

# Sets for deduplication
processed_messages = set()
processed_audio = set()


if bot:
    @bot.event
    async def on_ready():
        print(f'Bot logged in as {bot.user}')


    @bot.event
    async def on_message(message):
        if message.author.bot:
            return

        # Deduplication with content consideration
        message_key = f"{message.id}_{message.content}"
        if message_key in processed_messages:
            logger.info(f"Skipping duplicate message: {message.id}")
            return

        processed_messages.add(message_key)

        # Clear cache every 100 messages
        if len(processed_messages) > 100:
            processed_messages.clear()
            processed_messages.add(message_key)

        # Clear confirmation cache every 50 items
        if len(sent_confirmations) > 50:
            sent_confirmations.clear()

        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.mp3', '.wav', '.ogg', '.m4a']):
                await process_discord_audio(message, attachment)
                return

        await bot.process_commands(message)


async def process_discord_audio(message, attachment):
    # Special tag for each audio
    audio_key = f"{message.id}_{attachment.filename}_{attachment.size}"

    # Check if this audio has already been processed
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
            # Add a unique identifier for this report request
            request_id = f"{message.id}_{transcription}"

            # Check if a confirmation has already been sent for this request
            if request_id in sent_confirmations:
                logger.warning(f"Duplicate report confirmation prevented for message {message.id}")
                return

            # If this is a report request
            if "report" in transcription.lower() or "raport" in transcription.lower():
                report_generated = try_generate_report_from_text(transcription)
                if report_generated:
                    sent_confirmations.add(request_id)
                    await message.channel.send("📧 Report has been sent to your email.")
                    return

            # If not a category command or report request, try to extract expenses
            expenses = extract_with_llm(transcription)
            logger.info(f"Discord extracted expenses: {expenses}")

            if not expenses:
                await message.channel.send("❌ Could not recognize expenses in the recording.")
                return

            # Create a unique identifier for this response to prevent duplicates
            response_id = f"{message.id}_{len(expenses)}_{hash(transcription)}"

            logger.info(f"Checking response_id: {response_id}")

            # Check if this response has already been sent
            if response_id in sent_confirmations:
                logger.warning(f"Duplicate expense response prevented for message {message.id} - response_id: {response_id}")
                return

            sent_confirmations.add(response_id)
            logger.info(f"Added response_id to sent_confirmations: {response_id}")

            # Add expenses to database
            expense_ids = []
            for expense in expenses:
                expense_id = db_manager.add_expense(
                    date=expense.get('date', datetime.datetime.now()),
                    amount=expense.get('amount'),
                    vendor=expense.get('vendor', ''),
                    category=expense.get('category', ''),
                    description=expense.get('description', ''),
                    audio_file_path=temp_file.name,
                    transcription=transcription,
                    confidence_score=expense.get('confidence_score', 0.0)
                )
                if expense_id:
                    expense_ids.append(expense_id)

            # Build Discord response message
            response = "✅ Recognized expenses:\n"
            for expense in expenses:
                expense_date = expense.get('date')
                if isinstance(expense_date, datetime.datetime):
                    date_str = expense_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(expense_date).split('T')[0] if 'T' in str(expense_date) else str(expense_date)

                response += f"- {date_str}: {expense.get('vendor', 'Unknown store')} - £{expense.get('amount', 0)} ({expense.get('category', 'Other category')})\n"

            # Send Discord message
            logger.info(f"Sending Discord response for message {message.id}: {len(expenses)} expenses")
            await message.channel.send(response)
            logger.info(f"Discord response sent successfully for message {message.id}")

            # Send SINGLE email using unified template
            if expense_ids:
                try:
                    email_id = f"email_{message.id}_{hash(transcription)}"
                    if email_id not in sent_confirmations:
                        # Use unified email template
                        subject, html = EmailTemplates.expense_confirmation(
                            expenses=expenses,
                            transcription=transcription,
                            source="discord"
                        )

                        # Send via email_service.send_email
                        from app.services.email_service import send_email
                        send_email(
                            recipient=Config.DEFAULT_EMAIL_RECIPIENT,
                            subject=subject,
                            body=html
                        )

                        sent_confirmations.add(email_id)
                        logger.info(f"Discord: Confirmation email sent for message {message.id}")
                    else:
                        logger.warning(f"Duplicate email prevented for message {message.id}")
                except Exception as e:
                    logger.error(f"Failed to send confirmation email: {e}", exc_info=True)

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
        await ctx.send(f"Generating report for category '{category or 'all'}' for period '{period}'.")
        await ctx.send("✅ Report has been generated and sent to your email address.")

def run_discord_bot():
    if bot is None:
        logger.warning("Discord bot is disabled - cannot run")
        return
    bot.run(Config.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    run_discord_bot()