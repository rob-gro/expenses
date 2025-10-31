import logging
import os
import subprocess
import tempfile

from openai import OpenAI

from app.config import Config

# Configure logging
logger = logging.getLogger(__name__)


def convert_audio_to_wav(input_file):
    """Convert audio file to WAV format for better compatibility with Whisper"""
    try:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(tempfile.gettempdir(), f"{base_name}.wav")

        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("ffmpeg not found - skipping audio conversion")
            return input_file

        # Use ffmpeg to convert the file
        result = subprocess.run([
            'ffmpeg', '-i', input_file,
            '-ar', '16000',  # 16kHz sampling rate
            '-ac', '1',  # mono
            '-c:a', 'pcm_s16le',  # 16-bit PCM encoding
            output_file
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        logger.info(f"Successfully converted {input_file} to {output_file}")
        return output_file

    except subprocess.CalledProcessError as e:
        logger.error(f"Error converting audio: {str(e)}")
        return input_file
    except Exception as e:
        logger.error(f"Unexpected error during audio conversion: {str(e)}", exc_info=True)
        return input_file


def transcribe_audio(audio_file_path):
    """
    Transcribe audio file using OpenAI Whisper API
    Returns the transcription text
    """
    try:
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        # Convert audio to WAV format if needed
        file_ext = os.path.splitext(audio_file_path)[1].lower()
        if file_ext != '.wav':
            audio_file_path = convert_audio_to_wav(audio_file_path)

        # Open the audio file
        with open(audio_file_path, "rb") as audio_file:
            # Call the OpenAI Whisper API
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                language="pl"
            )

        # Log and return the transcription
        transcription = response
        logger.info(f"Transcription successful: {transcription[:100]}...")
        return transcription

    except Exception as e:
        logger.error(f"Transcription error: {str(e)}", exc_info=True)
        raise
