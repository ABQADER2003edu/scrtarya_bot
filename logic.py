import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from handlers.message_handler import handle_message, handle_confirmation
from handlers.voice_handler import handle_voice
from utils.scheduler import setup_morning_scheduler

logger = logging.getLogger(__name__)


class TokenFilter(logging.Filter):
    """Filter to mask the bot token in logs"""
    def filter(self, record):
        if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN in record.getMessage():
            record.msg = record.msg.replace(TELEGRAM_BOT_TOKEN, "[HIDDEN_TOKEN]")
            # Also handle if the token is in arguments
            if isinstance(record.args, tuple):
                 record.args = tuple(
                     arg.replace(TELEGRAM_BOT_TOKEN, "[HIDDEN_TOKEN]") 
                     if isinstance(arg, str) else arg 
                     for arg in record.args
                 )
        return True

# Apply filter to httpx logger
httpx_logger = logging.getLogger("httpx")
httpx_logger.addFilter(TokenFilter())
httpx_logger.setLevel(logging.INFO) # Show logs as requested, but filtered


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    if update.effective_user.id != TELEGRAM_CHAT_ID:
        return
    await update.message.reply_text(
        "👋 مرحباً! أنا بوت إدارة التقويم الخاص بك.\n\n"
        "يمكنك:\n"
        "• أضف موعد طبيب غداً الساعة 3\n"
        "• احذف اجتماع العمل\n"
        "• رحل موعد الدكتور ساعتين\n"
        "• إرسال رسالة صوتية بأمرك\n"
        "• قل 'صباح الجمال' لرسالة صباحية مع الطقس"
    )


async def smart_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route messages - Check for confirmation pending first"""
    # Try handling confirmation first
    handled = await handle_confirmation(update, context)
    # If not a confirmation response, handle as normal message
    if not handled:
        await handle_message(update, context)


def register_handlers(application: Application) -> None:
    """Adds command/message handlers. Safe to call before the event loop starts
    (does NOT touch the scheduler - see start_scheduler)."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, smart_message_router)
    )
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    logger.info("✅ Secretary Bot handlers registered!")


async def start_scheduler(application: Application) -> None:
    """Starts the morning-message scheduler. Must run inside a live asyncio
    loop, so it's called from Application's post_init (not from register_handlers)."""
    scheduler = setup_morning_scheduler(application)
    application.bot_data["scheduler"] = scheduler
    logger.info("✅ Morning scheduler started!")
