"""التسعير الإقليمي — ثلاث مناطق بأسعار اعتمدها المالك (٢٥ أغسطس).

المصدر الوحيد لأسعار المناطق: الرئيسية والتسجيل وget_plans كلهم بيقرأوا
من هنا، فمستحيل يعلنوا سعرين مختلفين. أسعار المنطقة الخليجية هي نفسها
أسعار SaaS Plan في القاعدة (الريال هو الأساس) — الخريطتان هنا تغطيان
مصر (جنيه) والأردن/العراق (دولار).

مجهول البلد ⟵ الخليج (أعلى تسعيرة — لا حافز للتحايل، راجع geo.py).
"""

REGION_BY_COUNTRY = {
    "Saudi Arabia": "gulf",
    "United Arab Emirates": "gulf",
    "Kuwait": "gulf",
    "Qatar": "gulf",
    "Bahrain": "gulf",
    "Oman": "gulf",
    "Egypt": "egypt",
    "Jordan": "levant",
    # العراق بتسعيرة الخليج بقرار المالك (٢٥ أغسطس، بعد دراسة التسعير):
    # MyFatoorah لا تدعم العراق فلا معنى لأسعار دولار معلنة لا تُحصَّل —
    # العراقي يشوف الريال ويسجل، والتحصيل تحويل بنكي يدوي.
    "Iraq": "gulf",
}

# باقة ⟵ منطقة ⟵ (السعر الشهري، العملة). الخليج يُقرأ من القاعدة مباشرة.
# سلم فئة الـERP الكامل (قرار المالك ٢٥ أغسطس بعد مراجعة D365/SAP/NetSuite/
# Odoo/SMACC): الخليج 299/699/1499 ر.س — ومصر والأردن بنفس نسب السلم
# السابق (~٣٨٪ للجنيه و~٧٥٪ للدولار من المكافئ).
REGIONAL_PRICES = {
    "Horizon Basic": {"egypt": (1499, "EGP"), "levant": (59, "USD")},
    "Horizon Pro": {"egypt": (3499, "EGP"), "levant": (139, "USD")},
    "Horizon Enterprise": {"egypt": (7499, "EGP"), "levant": (299, "USD")},
}


def region_for(country: str) -> str:
    return REGION_BY_COUNTRY.get(country or "", "gulf")


def localize_plan(plan: dict, country: str) -> dict:
    """يستبدل سعر/عملة الباقة بسعر منطقة البلد — الخليج يمرّ كما هو."""
    region = region_for(country)
    override = REGIONAL_PRICES.get(plan.get("name"), {}).get(region)
    if override:
        plan["monthly_price"], plan["currency"] = override
    return plan
