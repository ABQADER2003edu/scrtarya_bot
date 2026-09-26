"""Secretary Bot (calendar assistant) - standalone entry point."""
import logging
import sys

from telegram import Update
from telegram.ext import ApplicationBuilder

import config
from logic import register_handlers, start_scheduler

log = logging.getLogger("bot")


def main():
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not config.TELEGRAM_BOT_TOKEN:
        log.critical("BOT_TOKEN is missing - set it in .env or the Railway variables")
        sys.exit(1)
    if not config.TELEGRAM_CHAT_ID:
        log.critical("TELEGRAM_CHAT_ID is missing - set it in .env or the Railway variables")
        sys.exit(1)
    if not config.GEMINI_API_KEY:
        log.critical("GEMINI_API_KEY is missing - set it in .env or the Railway variables")
        sys.exit(1)
    if not config.GOOGLE_CALENDAR_ID:
        log.critical("GOOGLE_CALENDAR_ID is missing - set it in .env or the Railway variables")
        sys.exit(1)

    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(60)
        .post_init(start_scheduler)
        .build()
    )
    register_handlers(app)
    app.run_polling(timeout=30, allowed_updates=[Update.MESSAGE])


if __name__ == "__main__":
    main()
