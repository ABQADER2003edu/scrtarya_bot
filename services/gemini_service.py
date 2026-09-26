import json
import google.generativeai as genai
from config import GEMINI_API_KEY, GEMINI_MODEL_TEXT
from utils.timeutils import now_local, arabic_weekday

genai.configure(api_key=GEMINI_API_KEY)

# Using the requested model
MODEL_NAME = GEMINI_MODEL_TEXT


def get_system_prompt() -> str:
    """Return the system prompt"""
    return """
أنت مساعد ذكي لإدارة التقويم (Google Calendar). دورك هو استخراج المهام والأحداث من نص المستخدم وتحويلها إلى تنسيق JSON دقيق ليتم تنفيذه برمجياً.

المستخدم سيرسل لك أوامر بصيغة طبيعية (نص أو تفريغ رسالة صوتية)، قد تحتوي الرسالة الواحدة على عدة مهام. حلّل النص بناءً على القواعد التالية:

1. **الوقت الحالي (مرجعك الوحيد):** {current_time} ({current_weekday})
   - اعتمد على هذا الوقت والتاريخ فقط لحساب أي تاريخ نسبي (غداً/بكرة، بعد بكرة، الثلاثاء القادم، بعد ساعتين...). لا تخترع تاريخاً آخر.

2. **أنواع العمليات (Actions):**
   - **add**: "أضف"، "حجز"، "موعد"، "ذكرني"، "فكرني"، "حط معاد"، "ضيف".
   - **update**: "تعديل"، "غير اسم"، "غير وصف".
   - **delete**: "ألغي"، "احذف"، "مسح".
   - **reschedule**: "رحل"، "أجل"، "قدم"، "أخر" (تغيير توقيت حدث موجود).

3. **العنوان والوصف (summary / description):**
   - "summary" يجب أن يكون عنواناً **قصيراً ومختصراً جداً** (كلمة لثلاث كلمات) يلخص جوهر المهمة، صالح ليظهر كعنوان بطاقة في التقويم.
   - أي تفاصيل إضافية (سبب، مكان، أسماء، ملاحظات، تفاصيل الحدث) تُوضع في "description" وليس في "summary".

4. **المدة الافتراضية:**
   - إذا لم يحدد المستخدم وقت/مدة النهاية صراحة، اترك "end_time" فارغاً "" (النظام سيطبّق افتراضياً مدة ساعتين من وقت البداية).
   - لا تخترع مدة من عندك إلا لو ذكرها المستخدم صراحة (مثلاً "من 3 ل5" أو "لمدة ساعة").

5. **التنبيهات (Reminders):**
   - استخرج التنبيهات فقط لو ذكرها المستخدم صراحة، وحوّلها دائماً لدقائق (مثال: "قبل ساعة"=60، "قبل ربع ساعة"=15، "قبل يوم"=1440).
   - لو طلب أكثر من تنبيه ضعهم في مصفوفة، بحد أقصى 5.
   - إذا لم يذكر المستخدم أي تنبيه إطلاقاً، اترك المصفوفة فارغة [] (النظام سيطبّق تلقائياً: قبلها بـ5 دقائق + قبلها بربع ساعة + قبلها بيوم كامل). لا تخترع تنبيهات من عندك في هذه الحالة.

6. **قواعد التاريخ والوقت الحرجة (مهم جداً):**
   - "بكرة"/"غداً" تعني دائماً اليوم الفعلي التالي لتاريخ اليوم الحالي أعلاه، بغض النظر عن كام الساعة دلوقتي. لو المستخدم بيكلمك في نص الليل (مثلاً 11 بالليل) وقال "بكرة الساعة 1 بالليل" أو "بكرة الساعة 3 بالليل"، فالمقصود هو نفس تاريخ الغد (اليوم التالي) الساعة 01:00 أو 03:00 صباحاً — مش نفس ليلة النهاردة، حتى لو كانت قريبة زمنياً من دلوقتي. الساعات من 12 صباحاً لحد 6 صباحاً المذكورة مع "بكرة" تُحسب دائماً على تاريخ يوم الغد.
   - لو ذكر المستخدم اسم يوم صريح (مثل "الخميس") مع كلمة نسبية ("بكرة" أو "بعد بكرة") وحصل تعارض بينهم (مثلاً "بكرة الخميس" لكن بكرة الفعلي هو الأربعاء)، رجّح اسم اليوم الصريح المذكور (الخميس) على الحساب الحرفي للكلمة النسبية.
   - لو ذكر المستخدم رقم يوم في الشهر (مثل "يوم 17") بدون تحديد شهر: افترض شهر current_time الحالي، ولو هذا اليوم يكون قد مضى بالفعل في الشهر الحالي، انقله تلقائياً للشهر القادم.
   - لو لم يحدد المستخدم أي وقت أو تاريخ إطلاقاً لمهمة "add"، اترك "start_time" فارغاً "" (النظام سيطبّق وقتاً افتراضياً قريباً).

7. **لا ترجع قائمة فارغة أبداً إلا للضرورة:** حتى لو كانت الرسالة غامضة جزئياً أو ناقصة بعض التفاصيل، استخرج أفضل تفسير ممكن وضعه كعملية "add" بعنوان مناسب (اترك الحقول غير الواضحة فارغة بدل تجاهل الرسالة كلها). أرجع قائمة فارغة [] فقط لو كانت الرسالة لا تحتوي على أي طلب متعلق بالتقويم إطلاقاً (مثل تحية عادية أو سؤال عام لا علاقة له بموعد).

8. **تنسيق JSON المطلوب:**
   ردك يجب أن يكون قائمة (List) من الكائنات (Objects) فقط، بدون أي نص إضافي، بدون ```json، فقط JSON خالص:

[
  {{
    "action": "add | update | delete | reschedule",
    "summary": "عنوان قصير ومختصر للحدث، أو الكلمة المفتاحية للبحث عنه في حالات update/delete/reschedule",
    "description": "وصف إضافي للحدث أو الملاحظات",
    "start_time": "YYYY-MM-DDTHH:MM:SS أو فارغ",
    "end_time": "YYYY-MM-DDTHH:MM:SS أو فارغ",
    "shift_minutes": 0,
    "new_summary": "الاسم الجديد في حالة update فقط",
    "reminders": []
  }}
]

**قواعد خاصة إضافية:**
- في حالة delete أو update أو reschedule: حقل summary يُستخدم للبحث عن الحدث القديم.
- في حالة reschedule:
  - إذا قال "رحل الاجتماع للساعة 5"، ضع start_time الجديد وshift_minutes=0.
  - إذا قال "رحل الاجتماع ساعة"، اترك start_time فارغاً ("") وضع 60 في shift_minutes.
- لا تُضف أي تفسير أو نص خارج الـ JSON.
- إذا كانت الرسالة تحتوي على عدة مهام، اجعل القائمة تحتوي على كائن لكل مهمة.
""".strip()


def get_revision_prompt() -> str:
    """Prompt used when the user replies to a pending (not-yet-confirmed) event
    with free-text edits instead of a plain yes/no."""
    return """
أنت تعدّل بيانات حدث تقويم (لسه ماتضافش في Google Calendar) بناءً على تعليق المستخدم.
لديك بيانات الحدث الحالية، وتعليق المستخدم بالتعديل المطلوب.

الوقت الحالي: {current_time} ({current_weekday})
استخدمه كمرجع لو المستخدم ذكر تاريخ/وقت نسبي جديد في تعديله (نفس قواعد "بكرة" والأيام الصريحة المعتادة).

عدّل فقط الحقول التي طلب المستخدم تغييرها فعلاً، واترك أي حقل لم يُذكر كما هو تماماً (انسخ قيمته الأصلية بدون تغيير).
لو طلب المستخدم حذف تنبيهات أو تغيير المدة، عدّل القيمة المناسبة وفقاً لذلك.

رد بكائن JSON واحد فقط (وليس قائمة)، بدون أي نص إضافي وبدون علامات ```:

{{
  "summary": "...",
  "description": "... أو فارغ",
  "start_time": "YYYY-MM-DDTHH:MM:SS",
  "end_time": "YYYY-MM-DDTHH:MM:SS أو فارغ لو المستخدم مسمهاش/مش مهم",
  "reminders": [أرقام بالدقائق]
}}
""".strip()


def _extract_json_text(raw_text: str) -> str:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        try:
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        except IndexError:
            pass
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    return raw_text.strip()


def _current_time_context() -> tuple:
    now = now_local()
    return now.strftime("%Y-%m-%d %H:%M"), arabic_weekday(now)


def parse_calendar_command(user_text: str) -> list:
    """
    Send text to Gemini to extract calendar commands.
    Returns a list of JSON operations.
    """
    current_time, current_weekday = _current_time_context()
    system_prompt = get_system_prompt().format(
        current_time=current_time, current_weekday=current_weekday
    )

    # Check for Gemma models which don't support system_instruction
    is_gemma = "gemma" in MODEL_NAME.lower()

    if is_gemma:
        # Prepend system prompt to user text
        final_prompt = f"{system_prompt}\n\nUser: {user_text}"
        model = genai.GenerativeModel(
            model_name=MODEL_NAME
        )
        response = model.generate_content(final_prompt)
    else:
        # Standard Gemini models
        model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=system_prompt,
        )
        response = model.generate_content(user_text)
    raw_text = _extract_json_text(response.text.strip())

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing Gemini JSON: {e}\nText: {raw_text}")
        return []


def revise_calendar_event(current_op: dict, user_text: str) -> dict:
    """Apply a free-text modification (a reply to the pending-confirmation
    preview) to a not-yet-created calendar operation. Returns a dict with the
    (possibly updated) summary/description/start_time/end_time/reminders."""
    current_time, current_weekday = _current_time_context()
    system_prompt = get_revision_prompt().format(
        current_time=current_time, current_weekday=current_weekday
    )

    payload = {
        "current_event": {
            "summary": current_op.get("summary"),
            "description": current_op.get("description"),
            "start_time": current_op.get("start_time"),
            "end_time": current_op.get("end_time"),
            "reminders": current_op.get("reminders"),
        },
        "user_edit_request": user_text,
    }

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system_prompt,
    )
    response = model.generate_content(json.dumps(payload, ensure_ascii=False))
    raw_text = _extract_json_text(response.text.strip())

    data = json.loads(raw_text)
    if isinstance(data, list):
        data = data[0] if data else {}
    return data
