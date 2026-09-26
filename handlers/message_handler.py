import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from services.gemini_service import parse_calendar_command, revise_calendar_event
from services.calendar_service import (
    add_event, delete_event, reschedule_event,
    update_event, check_conflicts
)
from config import TELEGRAM_CHAT_ID
from calendar_bot.logic import identify_category
from utils.timeutils import now_local, arabic_weekday

DEFAULT_DURATION_HOURS = 2
DEFAULT_REMINDERS = [5, 15, 1440]  # 5 mins before, 15 mins before, 1 day before

APPROVE_WORDS = {
    "تمام", "نعم", "أيوه", "ايوه", "تأكيد", "أكد", "اكد",
    "موافق", "yes", "ok", "اوكي", "أوكي", "يلا", "confirm", "تمام ✅",
}
REJECT_WORDS = {
    "لا", "رفض", "إلغاء", "الغاء", "no", "cancel", "لا ❌", "الغي",
}


def _strip_button_emoji(text: str) -> str:
    return text.replace("✅", "").replace("❌", "").strip()


def _is_approval(text: str) -> bool:
    return _strip_button_emoji(text).strip().lower() in APPROVE_WORDS


def _is_rejection(text: str) -> bool:
    return _strip_button_emoji(text).strip().lower() in REJECT_WORDS


def _normalize_time_fields(op: dict) -> None:
    """Fill in ISO formatting + apply the default 2-hour duration when the
    user (or Gemini) didn't specify an end time."""
    start_time = (op.get("start_time") or "").strip()
    end_time = (op.get("end_time") or "").strip()

    if not start_time:
        start_dt = now_local() + datetime.timedelta(minutes=10)
    else:
        if "T" not in start_time:
            start_time = start_time.replace(" ", "T")
        if len(start_time.split(":")) == 2:
            start_time += ":00"
        start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", ""))

    if end_time:
        if "T" not in end_time:
            end_time = end_time.replace(" ", "T")
        if len(end_time.split(":")) == 2:
            end_time += ":00"
        end_dt = datetime.datetime.fromisoformat(end_time.replace("Z", ""))
    else:
        end_dt = start_dt + datetime.timedelta(hours=DEFAULT_DURATION_HOURS)

    if end_dt <= start_dt:
        end_dt += datetime.timedelta(days=1)

    op["start_time"] = start_dt.isoformat()
    op["end_time"] = end_dt.isoformat()


def _normalize_reminders(op: dict) -> None:
    reminders = op.get("reminders")
    if not reminders:
        reminders = DEFAULT_REMINDERS.copy()
    op["reminders"] = list(reminders)[:5]


def _refresh_conflicts(op: dict) -> None:
    try:
        conflicts = check_conflicts(op["start_time"], op["end_time"])
        op["conflicts"] = [c.get("summary", "بدون عنوان") for c in conflicts]
    except Exception:
        op["conflicts"] = []


def _format_reminders(reminders: list) -> str:
    parts = []
    for m in reminders:
        m = int(m)
        if m >= 1440 and m % 1440 == 0:
            days = m // 1440
            parts.append(f"قبلها بـ{days} يوم" if days == 1 else f"قبلها بـ{days} أيام")
        elif m >= 60 and m % 60 == 0:
            hrs = m // 60
            parts.append(f"قبلها بـ{hrs} ساعة")
        else:
            parts.append(f"قبلها بـ{m} دقيقة")
    return "، ".join(parts) if parts else "بدون تنبيهات"


def _format_duration(start_dt: datetime.datetime, end_dt: datetime.datetime) -> str:
    total_minutes = int((end_dt - start_dt).total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} ساعة")
    if minutes:
        parts.append(f"{minutes} دقيقة")
    return " و".join(parts) if parts else "أقل من دقيقة"


def _format_preview(op: dict) -> str:
    start_dt = datetime.datetime.fromisoformat(op["start_time"])
    end_dt = datetime.datetime.fromisoformat(op["end_time"])

    lines = [
        "📝 *مراجعة قبل الإضافة:*",
        f"• *العنوان:* {op.get('summary') or 'بدون عنوان'}",
        f"• *التاريخ:* {start_dt.strftime('%Y-%m-%d')} ({arabic_weekday(start_dt)})",
        f"• *الوقت:* {start_dt.strftime('%H:%M')} ← {end_dt.strftime('%H:%M')}",
        f"• *المدة:* {_format_duration(start_dt, end_dt)}",
        f"• *التنبيهات:* {_format_reminders(op.get('reminders', []))}",
        f"• *الفئة:* {op.get('category_name') or 'بدون فئة'}",
    ]
    if op.get("description"):
        lines.append(f"• *ملاحظات:* {op['description']}")
    if op.get("conflicts"):
        lines.append(f"\n⚠️ *فيه تعارض مع:* {', '.join(op['conflicts'])}")
    lines.append(
        "\nابعت *تمام* للتأكيد، أو *لا* للإلغاء، أو اكتب تعديلك مباشرة "
        "(مثلاً: «خليها الساعة 5» أو «غيّر العنوان لكذا» أو «شيل التنبيه اللي قبل يوم»)."
    )
    return "\n".join(lines)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = None):
    """Main message handler with multi-operation support"""

    if update.effective_user.id != TELEGRAM_CHAT_ID:
        await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
        return

    user_text = text or update.message.text

    if "صباح الجمال" in user_text or "صباح الكريستال" in user_text:
        from utils.scheduler import send_morning_message
        await send_morning_message(context.bot)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    operations = parse_calendar_command(user_text)
    if not operations:
        # One retry with a nudge before giving up - avoids bailing on a
        # slightly-oddly-phrased message.
        operations = parse_calendar_command(
            f"{user_text}\n\n(تذكير: استخرج أفضل تفسير ممكن كعملية add، ولا ترجع "
            "قائمة فارغة إلا لو الرسالة فعلاً مفيهاش أي طلب متعلق بالتقويم)"
        )

    if not operations:
        await update.message.reply_text(
            "🤔 معنديش تفاصيل كفاية عشان أظبط الموعد.\n"
            "ممكن تقولها بصيغة زي: «حط معاد [العنوان] يوم [التاريخ/اليوم] الساعة [الوقت]»؟"
        )
        return

    pending_ops = []
    results = []

    for op in operations:
        action = op.get("action", "add") or "add"
        summary = (op.get("summary") or "").strip() or "بدون عنوان"
        op["summary"] = summary

        category_name, color_id = identify_category(
            f"{summary} {op.get('description') or ''} {user_text}"
        )
        op["category_name"] = category_name
        op["color_id"] = color_id

        if action == "add":
            try:
                _normalize_time_fields(op)
                _normalize_reminders(op)
                _refresh_conflicts(op)
                pending_ops.append(op)
            except Exception as e:
                results.append(f"❌ خطأ في تجهيز '{summary}': {str(e)}")
        elif action == "delete":
            results.append(delete_event(summary))
        elif action == "reschedule":
            results.append(
                reschedule_event(summary, op.get("start_time") or None, op.get("shift_minutes", 0))
            )
        elif action == "update":
            results.append(update_event(summary, op.get("new_summary")))
        else:
            results.append(f"❓ عملية غير معروفة لـ '{summary}'")

    # Send immediate results for delete/update/reschedule ops
    if results:
        await update.message.reply_text("\n\n".join(results), parse_mode="Markdown")

    # Every "add" now goes through the confirm/edit/reject preview before touching the calendar
    if pending_ops:
        context.user_data["pending_queue"] = pending_ops
        await process_next_pending(update, context)


async def process_next_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the confirmation preview for the next queued 'add' operation."""
    queue = context.user_data.get("pending_queue", [])
    if not queue:
        context.user_data.pop("pending_queue", None)
        context.user_data.pop("interaction_type", None)
        return

    op = queue[0]
    preview = _format_preview(op)
    reply_keyboard = [["تمام ✅", "لا ❌"]]
    await update.message.reply_text(
        preview,
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
        parse_mode="Markdown",
    )
    context.user_data["interaction_type"] = "confirm_add"


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles replies while an 'add' operation is pending confirmation:
    approve it, reject it, or apply a free-text edit and show the preview again."""
    if update.effective_user.id != TELEGRAM_CHAT_ID:
        return False

    queue = context.user_data.get("pending_queue")
    interaction_type = context.user_data.get("interaction_type")
    if not queue or interaction_type != "confirm_add":
        return False

    user_text = update.message.text.strip()
    op = queue[0]

    if _is_approval(user_text):
        try:
            created = add_event(
                op["summary"], op["start_time"], op["end_time"],
                op.get("reminders"), op.get("description"), op.get("color_id"),
            )
            await update.message.reply_text(
                f"✅ تمت إضافة *{created.get('summary', op['summary'])}*",
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ خطأ أثناء الإضافة: {str(e)}", reply_markup=ReplyKeyboardRemove()
            )
        queue.pop(0)
        await process_next_pending(update, context)
        return True

    if _is_rejection(user_text):
        queue.pop(0)
        await update.message.reply_text(
            f"❌ تم إلغاء '{op['summary']}'", reply_markup=ReplyKeyboardRemove()
        )
        await process_next_pending(update, context)
        return True

    # Anything else is treated as a free-text edit request on the pending event
    try:
        updates = revise_calendar_event(op, user_text)
        for key in ("summary", "description", "start_time", "end_time", "reminders"):
            if key in updates and updates[key] not in (None, ""):
                op[key] = updates[key]
        _normalize_time_fields(op)
        _normalize_reminders(op)
        _refresh_conflicts(op)
    except Exception as e:
        await update.message.reply_text(f"❌ معرفتش أطبّق التعديل: {str(e)}")
        return True

    await process_next_pending(update, context)
    return True
