"""
All customer-facing email copy, in one place.

Why a module and not inline strings: the wording IS the product's voice. Keeping
it here means copy can be reviewed and edited without touching provisioning or
billing logic, and every message renders through the same branded shell.

Voice rules (Horizon brand book):
  - الاء speaks in first person, Egyptian-leaning Modern Standard Arabic: warm,
    short sentences, no corporate padding.
  - Say what happened and what the reader does next. One action per email.
  - Navy #1D2D44 is the voice. Blue #5083BC appears ONLY on success.
    Amber #B8860B for time-sensitive warnings, red #B04A3F for stopped service.
  - Never blame the customer. A suspended account is a state, not a verdict.
  - Every email is readable as plain text if images/CSS are stripped.
"""

import frappe
from frappe.utils import escape_html

BRAND = "Horizon AI Powered ERP"
SIGNATURE = "الاء — الوكيل الذكي | Horizon Smart Systems"

NAVY = "#1D2D44"
BLUE = "#5083BC"       # success only
AMBER = "#B8860B"      # warning
RED = "#B04A3F"        # stopped
INK = "#221f1f"
MUTED = "#4A5361"
LINE = "#E3E5E0"
PAPER = "#F7F8F6"


# ------------------------------------------------------------------ #
# shell
# ------------------------------------------------------------------ #

def _shell(title: str, body_html: str, accent: str = NAVY,
           cta_label: str = "", cta_url: str = "") -> str:
    """Wrap copy in the Horizon email shell. Table-based for mail-client safety."""
    cta = ""
    if cta_label and cta_url:
        cta = f"""
        <tr><td style="padding:6px 0 4px">
          <a href="{cta_url}" style="display:inline-block;background:{accent};color:#ffffff;
             font-weight:700;font-size:15px;text-decoration:none;border-radius:12px;
             padding:13px 30px">{cta_label}</a>
        </td></tr>"""

    return f"""<div dir="rtl" style="background:{PAPER};padding:24px 12px;margin:0">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center"
         style="max-width:560px;width:100%;background:#ffffff;border:1px solid {LINE};
                border-radius:16px;border-top:4px solid {accent};
                font-family:Cairo,'Segoe UI',Arial,sans-serif;color:{INK}">
    <tr><td style="padding:26px 28px 0">
      <div style="font-size:13px;font-weight:800;color:{NAVY};letter-spacing:.2px">
        Horizon <span style="color:{MUTED};font-weight:700">| AI Powered ERP</span>
      </div>
    </td></tr>
    <tr><td style="padding:14px 28px 0">
      <h1 style="margin:0;font-size:21px;font-weight:900;color:{accent};line-height:1.4">{title}</h1>
    </td></tr>
    <tr><td style="padding:12px 28px 20px;font-size:15px;line-height:1.95;color:{INK}">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        <tr><td style="font-size:15px;line-height:1.95">{body_html}</td></tr>
        {cta}
      </table>
    </td></tr>
    <tr><td style="padding:0 28px 24px">
      <div style="border-top:1px solid {LINE};padding-top:14px;font-size:12.5px;color:{MUTED};line-height:1.8">
        {escape_html(SIGNATURE)}<br>
        لو محتاج أي مساعدة، رد على الإيميل ده مباشرة.
      </div>
    </td></tr>
  </table>
</div>"""


def _url_box(url: str) -> str:
    return (f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:10px;'
            f'padding:11px 16px;margin:12px 0;direction:ltr;text-align:left;'
            f'font-family:monospace;font-size:13.5px;color:{NAVY};font-weight:600">{url}</div>')


def _credentials_box(email: str, password: str) -> str:
    return f"""<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;padding:14px 18px;margin:14px 0">
      <div style="font-size:12.5px;font-weight:800;color:{NAVY};margin-bottom:8px">بيانات الدخول</div>
      <div style="font-size:13.5px;color:{MUTED};line-height:2">
        المستخدم: <span style="direction:ltr;display:inline-block;font-family:monospace;color:{INK}">{escape_html(email)}</span><br>
        كلمة المرور: <span style="direction:ltr;display:inline-block;font-family:monospace;color:{INK}">{escape_html(password)}</span>
      </div>
      <div style="font-size:12px;color:{MUTED};margin-top:8px">غيّرها من أول دخول من الملف الشخصي.</div>
    </div>"""


def _send(doc, subject: str, html: str):
    try:
        frappe.sendmail(recipients=[doc.email], subject=subject, message=html)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Email failed: {getattr(doc, 'name', '?')}")


def _greet(doc) -> str:
    name = (getattr(doc, "contact_name", None) or "").strip()
    return f"أهلاً {escape_html(name.split()[0])}" if name else "أهلاً بك"


# ------------------------------------------------------------------ #
# 1) OTP — sent before the account exists
# ------------------------------------------------------------------ #

def send_otp(email: str, otp: str, minutes: int = 15):
    html = _shell(
        title="كود التأكيد",
        body_html=(
            "دخّل الكود ده في صفحة التسجيل عشان أبدأ تجهيز نظامك:"
            f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
            f'padding:18px;margin:16px 0;text-align:center">'
            f'<span style="font-family:monospace;font-size:32px;font-weight:700;'
            f'letter-spacing:10px;color:{NAVY};direction:ltr;display:inline-block">{escape_html(otp)}</span>'
            "</div>"
            f'<div style="font-size:13px;color:{MUTED}">صالح لمدة {minutes} دقيقة. '
            "لو مش إنت اللي طلبته، تجاهل الرسالة ومفيش حاجة هتحصل.</div>"
        ),
    )
    frappe.sendmail(recipients=[email], subject=f"كود التأكيد: {otp} | {BRAND}",
                    message=html, delayed=False)


# ------------------------------------------------------------------ #
# 2) Welcome — the site is live
# ------------------------------------------------------------------ #

def send_welcome(doc, owner_password: str, trial_days: int = 14):
    url = f"https://{doc.site_name}"
    body = (
        f"{_greet(doc)} 👋<br><br>"
        "أنا <b>الاء</b>، الوكيل الذكي في هورايزون. خلّصت تجهيز نسختك المستقلة من "
        f"<b>{BRAND}</b> وهي شغالة دلوقتي على العنوان ده:"
        + _url_box(url)
        + _credentials_box(doc.email, owner_password)
        + f'<div style="font-size:13.5px;color:{MUTED};line-height:2">'
        f"تجربتك المجانية <b>{trial_days} يوم</b> بدأت من دلوقتي — كل المميزات مفتوحة، "
        "وبياناتك في قاعدة بيانات معزولة تمامًا مع نسخة احتياطية يومية."
        "</div>"
    )
    _send(doc, f"نظامك جاهز ✅ | {BRAND}",
          _shell("نظامك جاهز 🎉", body, accent=BLUE,
                 cta_label="ادخل على نظامك", cta_url=url))


# ------------------------------------------------------------------ #
# 3) Expiry reminders — 7 / 3 / 1 days
# ------------------------------------------------------------------ #

def send_expiry_notice(doc, days: int, plan: str, ends_on,
                       pay_url: str = "", amount: str = ""):
    """days: 7 | 3 | 1. Tone tightens as the date approaches — never alarmist."""
    if days >= 7:
        title = "اشتراكك ينتهي بعد أسبوع"
        lead = ("حبيت أنبهك بدري عشان يبقى قدامك وقت. لسه كل حاجة شغالة عادي "
                "ومفيش أي تأثير على بياناتك.")
    elif days == 3:
        title = "٣ أيام على انتهاء اشتراكك"
        lead = "فاضل تلات أيام. التجديد بياخد دقيقة والنظام بيكمل شغله من غير أي انقطاع."
    else:
        title = "آخر يوم في اشتراكك"
        lead = ("النهارده آخر يوم. بعد الانتهاء عندك <b>3 أيام سماح</b> النظام فيها "
                "شغال عادي، وبعدها بيتوقف مؤقتًا لحد التجديد.")

    body = (
        f"{_greet(doc)}،<br><br>{lead}<br><br>"
        f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
        f'padding:14px 18px;margin:6px 0 4px;font-size:13.5px;color:{MUTED};line-height:2">'
        f"الباقة: <b style=\"color:{INK}\">{escape_html(plan)}</b><br>"
        f"تاريخ الانتهاء: <b style=\"color:{INK}\">{escape_html(str(ends_on))}</b>"
        + (f"<br>قيمة التجديد: <b style=\"color:{INK}\">{escape_html(amount)}</b>" if amount else "")
        + "</div>"
    )
    if pay_url:
        body += (f'<div style="font-size:13px;color:{MUTED};margin-top:10px">'
                 "الدفع آمن عبر MyFatoorah (مدى / Apple Pay / بطاقة) والتفعيل فوري وتلقائي. "
                 "التحويل البنكي متاح برضه لو تفضّله.</div>")

    accent = AMBER if days <= 3 else NAVY
    _send(doc, f"{title} | {BRAND}",
          _shell(title, body, accent=accent,
                 cta_label="جدّد الآن" if pay_url else "", cta_url=pay_url))


# ------------------------------------------------------------------ #
# 4) Payment received
# ------------------------------------------------------------------ #

def send_payment_confirmed(doc, invoice_name: str, amount: str, ends_on):
    body = (
        f"{_greet(doc)}،<br><br>"
        "استلمت الدفعة وفعّلت الاشتراك فورًا — مفيش أي إجراء مطلوب منك."
        f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
        f'padding:14px 18px;margin:14px 0;font-size:13.5px;color:{MUTED};line-height:2">'
        f"رقم الفاتورة: <b style=\"color:{INK}\">{escape_html(invoice_name)}</b><br>"
        f"المبلغ: <b style=\"color:{INK}\">{escape_html(amount)}</b><br>"
        f"الاشتراك ساري حتى: <b style=\"color:{INK}\">{escape_html(str(ends_on))}</b>"
        "</div>"
    )
    _send(doc, f"تم استلام الدفع ✅ | {BRAND}",
          _shell("تم تفعيل اشتراكك ✅", body, accent=BLUE,
                 cta_label="ادخل على نظامك", cta_url=f"https://{doc.site_name}"))


# ------------------------------------------------------------------ #
# 5) Suspended — service stopped, data safe
# ------------------------------------------------------------------ #

def send_suspended(doc, pay_url: str = ""):
    body = (
        f"{_greet(doc)}،<br><br>"
        "خلصت فترة السماح ووقفت النظام مؤقتًا لحين التجديد.<br><br>"
        f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
        f'padding:14px 18px;font-size:13.5px;color:{MUTED};line-height:2">'
        f"<b style=\"color:{INK}\">بياناتك كلها موجودة زي ما هي.</b> مفيش أي حاجة اتمسحت، "
        "والنسخ الاحتياطية شغالة عادي. أول ما تجدّد، النظام بيرجع بنفس البيانات في ثواني."
        "</div>"
    )
    _send(doc, f"تم إيقاف النظام مؤقتًا | {BRAND}",
          _shell("النظام متوقف مؤقتًا", body, accent=RED,
                 cta_label="جدّد وارجع للعمل" if pay_url else "", cta_url=pay_url))


# ------------------------------------------------------------------ #
# 6) Resumed
# ------------------------------------------------------------------ #

def send_resumed(doc):
    url = f"https://{doc.site_name}"
    body = (f"{_greet(doc)}،<br><br>"
            "رجعنا شغالين — النظام متاح دلوقتي بالكامل بنفس بياناتك ومستخدمينك."
            + _url_box(url))
    _send(doc, f"تم إعادة تفعيل نظامك ✅ | {BRAND}",
          _shell("رجعنا شغالين ✅", body, accent=BLUE,
                 cta_label="ادخل على نظامك", cta_url=url))


# ------------------------------------------------------------------ #
# 7) Plan changed
# ------------------------------------------------------------------ #

def send_plan_changed(doc, old_plan: str, new_plan: str, limits: dict | None = None):
    rows = ""
    for label, value in (limits or {}).items():
        rows += (f'<div style="font-size:13.5px;color:{MUTED};line-height:2">'
                 f"{escape_html(label)}: <b style=\"color:{INK}\">{escape_html(str(value))}</b></div>")
    body = (
        f"{_greet(doc)}،<br><br>"
        f"غيّرت باقتك من <b>{escape_html(old_plan)}</b> إلى <b>{escape_html(new_plan)}</b>، "
        "والحدود الجديدة سارية دلوقتي من غير ما تعمل أي حاجة."
        + (f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
           f'padding:14px 18px;margin:14px 0">{rows}</div>' if rows else "")
    )
    _send(doc, f"تم تحديث باقتك | {BRAND}",
          _shell("تم تحديث باقتك", body, accent=NAVY,
                 cta_label="ادخل على نظامك", cta_url=f"https://{doc.site_name}"))


# ------------------------------------------------------------------ #
# 8) Provisioning failed — internal-facing tone, no jargon dumped on the customer
# ------------------------------------------------------------------ #

def send_provisioning_failed(doc):
    body = (
        f"{_greet(doc)}،<br><br>"
        "حصلت مشكلة تقنية وأنا بجهّز نظامك، ووقفت العملية عشان مايتركّبش حاجة ناقصة.<br><br>"
        f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
        f'padding:14px 18px;font-size:13.5px;color:{MUTED};line-height:2">'
        "<b style=\"color:" + INK + "\">مفيش أي مبلغ اتخصم منك.</b> فريق هورايزون شايف المشكلة "
        "وهيتواصل معاك خلال ساعات قليلة بالحل أو ببديل."
        "</div>"
    )
    _send(doc, f"تأخير في تجهيز نظامك | {BRAND}",
          _shell("محتاج وقت إضافي", body, accent=AMBER))


# ------------------------------------------------------------------ #
# 9) Cost-calculator report — a marketing email, still in Alaa's voice
# ------------------------------------------------------------------ #

def send_calculator_report(lead):
    """Sent to a prospect right after they use the public calculator.
    Tone rule: they gave us a number they arrived at themselves — reflect it
    back honestly as an estimate, never as a promise of savings."""
    from frappe.utils import fmt_money

    seg = "المصنع" if lead.get("calc_mode") == "Manufacturing" else "المشاريع"
    amount = fmt_money(lead.estimate or 0, currency=lead.get("currency") or "SAR")
    plan_year = 2500 * 12
    ratio = (lead.estimate / plan_year) if lead.estimate else 0

    body = (
        f"أهلاً {escape_html((lead.contact_name or '').split()[0] if lead.contact_name else '')} 👋<br><br>"
        f"حسبت تقدير التسرب السنوي في {seg} وطلع:"
        f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
        f'padding:18px;margin:14px 0;text-align:center">'
        f'<div style="font-size:12.5px;font-weight:800;color:{MUTED}">تقدير التسرب السنوي</div>'
        f'<div style="font-size:30px;font-weight:900;color:{NAVY};margin-top:5px">{escape_html(amount)}</div>'
        "</div>"
        f'<div style="font-size:13.5px;color:{MUTED};line-height:2">'
        "الرقم ده <b>تقدير استرشادي</b> مبني على المدخلات اللي حطيتها ومتوسطات القطاع — مش وعد بعائد. "
        "قيمته الحقيقية إنه يوريك <b>فين</b> بيتسرب، عشان تقيسه بنفسك."
        "</div>"
    )
    if ratio > 1:
        body += (
            f'<div style="background:{PAPER};border:1px solid {LINE};border-radius:12px;'
            f'padding:14px 18px;margin:14px 0;font-size:13.5px;color:{MUTED};line-height:2">'
            f"للمقارنة: سنة كاملة من باقة Horizon Pro بـ <b style=\"color:{INK}\">{plan_year:,} ر.س</b> — "
            f"يعني النظام بيسدد تكلفته لو استرجع <b style=\"color:{INK}\">{100/ratio:.1f}%</b> من الرقم ده بس."
            "</div>"
        )
    body += (
        f'<div style="font-size:13.5px;color:{MUTED};line-height:2;margin-top:6px">'
        "لو حابب، أجهّزلك عرض توضيحي على حالتك تحديدًا — بنمشي سوا على دورة إنتاج أو مستخلص حقيقي من عندك."
        "</div>"
    )

    html = _shell("تقدير التسرب السنوي", body, accent=NAVY,
                  cta_label="ابدأ نسختك المجانية", cta_url="https://horizonerp.cloud/signup")
    _send(lead, f"تقدير التسرب السنوي: {amount} | {BRAND}", html)
