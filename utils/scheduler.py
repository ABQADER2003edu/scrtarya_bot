import datetime
from telegram import Bot
from services.calendar_service import get_today_events
from services.weather_service import get_sohag_weather
from config import TELEGRAM_CHAT_ID, TIMEZONE
from utils.timeutils import now_local


async def send_morning_message(bot: Bot):
    """Send morning message with weather and events"""

    # Fetch weather
    weather = get_sohag_weather()

    # Fetch today's events
    events = get_today_events()

    # Build events text
    if events:
        events_text = ""
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date", ""))
            if "T" in start:
                try:
                    time_str = datetime.datetime.fromisoformat(
                        start.replace("Z", "")
                    ).strftime("%H:%M")
                except ValueError:
                    time_str = "??"
            else:
                time_str = "طوال اليوم"
            events_text += f"  🗓 {event['summary']} — الساعة {time_str}\n"
    else:
        events_text = "  لا توجد أحداث مجدولة اليوم 🎉\n"

    today = now_local().strftime("%A، %d %B %Y")

    message = f"""
🌅 *صباح الخير!*
📅 *{today}*

━━━━━━━━━━━━━━━━━━━━━
🌡️ *درجات الحرارة في سوهاج اليوم:*

  {weather['morning']['emoji']} صباحاً (8:00): *{weather['morning']['temp']}°C*
  {weather['noon']['emoji']} ظهراً (13:00): *{weather['noon']['temp']}°C*
  {weather['night']['emoji']} ليلاً (22:00): *{weather['night']['temp']}°C*

━━━━━━━━━━━━━━━━━━━━━
📋 *أحداث اليوم:*
{events_text}
━━━━━━━━━━━━━━━━━━━━━
يوم موفق! 💪
""".strip()

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message,
        parse_mode="Markdown"
    )


def setup_morning_scheduler(app):
    """Setup scheduler for morning messages"""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from config import MORNING_MESSAGE_HOUR, MORNING_MESSAGE_MINUTE

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    async def morning_job():
        await send_morning_message(app.bot)

    scheduler.add_job(
        morning_job,
        trigger=CronTrigger(
            hour=MORNING_MESSAGE_HOUR,
            minute=MORNING_MESSAGE_MINUTE,
            timezone=TIMEZONE
        ),
    )

    scheduler.start()
    return scheduler
