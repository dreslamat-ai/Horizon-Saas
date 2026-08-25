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
    "Iraq": "levant",
}

# باقة ⟵ منطقة ⟵ (السعر الشهري، العملة). الخليج يُقرأ من القاعدة مباشرة.
REGIONAL_PRICES = {
    "Horizon Basic": {"egypt": (499, "EGP"), "levant": (19, "USD")},
    "Horizon Pro": {"egypt": (1299, "EGP"), "levant": (49, "USD")},
    "Horizon Enterprise": {"egypt": (2499, "EGP"), "levant": (99, "USD")},
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
