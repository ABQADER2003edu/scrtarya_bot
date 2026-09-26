import os
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from config import TELEGRAM_CHAT_ID

import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL_VOICE_LIST

genai.configure(api_key=GEMINI_API_KEY)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages"""

    if update.effective_user.id != TELEGRAM_CHAT_ID:
        await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
        return

    await update.message.reply_text("🎤 جاري تحليل الرسالة الصوتية...")

    voice = update.message.voice
    voice_file = await context.bot.get_file(voice.file_id)

    # Download voice file
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    await voice_file.download_to_drive(tmp_path)

    # Try each model in the list until one succeeds
    last_error = None
    for model_name in GEMINI_MODEL_VOICE_LIST:
        try:
            # Upload to Gemini for transcription
            audio_file = genai.upload_file(tmp_path, mime_type="audio/ogg")
            
            # Use the current model from the list
            model = genai.GenerativeModel(model_name)
            transcription_response = model.generate_content([
                "فرّغ هذه الرسالة الصوتية إلى نص عربي بدقة، ولا تضف أي تعليق:",
                audio_file
            ])

            transcribed_text = transcription_response.text.strip()

            # Update message text to be processed by message handler
            from .message_handler import handle_message
            await update.message.reply_text(f"📝 فهمت ({model_name}): _{transcribed_text}_", parse_mode="Markdown")
            await handle_message(update, context, text=transcribed_text)
            return

        except Exception as e:
            last_error = e
            print(f"Model {model_name} failed: {e}")
            continue

    # If all models failed
    if last_error:
         await update.message.reply_text(f"❌ خطأ في تحليل الصوت بعد تجربة كل الموديلات: {str(last_error)}")

    # Cleanup
    if os.path.exists(tmp_path):
            os.unlink(tmp_path)
