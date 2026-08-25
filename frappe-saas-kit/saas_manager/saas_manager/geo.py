"""تحديد بلد الزائر من عنوان IP — على الخادم حصرًا، بلا أي إدخال من العميل.

طلب المالك الصريح (٢٥ أغسطس): «عاوز البلد يتم جلبه من الموقع من خلال
الايبي ومش عاوز تلاعب من العملاء». من هنا:
- لا يُقرأ أي بلد من المتصفح إطلاقًا — الحقل اتشال من نموذج التسجيل.
- nginx يكتب X-Forwarded-For بـ$remote_addr (استبدالًا لا إلحاقًا) على
  مسارات التسجيل، فقيمة يرسلها العميل في الهيدر لا تصل أصلًا.
- مجهول البلد (IP خاص، بلد غير مغطى بأسعارنا، قاعدة مفقودة) ⟵ السعودية:
  أعلى تسعيرة، فلا يوجد أي حافز اقتصادي للتحايل على الاكتشاف.

القاعدة: DB-IP Country Lite (مجانية، تتحدث شهريًا) في
/home/frappe/geoip/dbip-country-lite.mmdb — تحديثها بإعادة تنزيل الملف.
"""

import frappe

GEOIP_DB = "/home/frappe/geoip/dbip-country-lite.mmdb"
DEFAULT_COUNTRY = "Saudi Arabia"

# ISO ⟵ اسم البلد كما في COUNTRY_DEFAULTS بالprovisioner (عملة/توقيت)
ISO_TO_COUNTRY = {
    "SA": "Saudi Arabia",
    "AE": "United Arab Emirates",
    "EG": "Egypt",
    "KW": "Kuwait",
    "QA": "Qatar",
    "BH": "Bahrain",
    "OM": "Oman",
    "JO": "Jordan",
    "IQ": "Iraq",
}

_reader = None


def _db():
    global _reader
    if _reader is None:
        import maxminddb
        _reader = maxminddb.open_database(GEOIP_DB)
    return _reader


def detect_country(ip: str | None = None) -> str:
    """بلد الطلب الحالي (أو IP معطى) — دائمًا يرجع اسمًا صالحًا للتسعير."""
    ip = ip or getattr(frappe.local, "request_ip", None)
    if not ip:
        return DEFAULT_COUNTRY
    try:
        data = _db().get(ip.strip()) or {}
        iso = (data.get("country") or {}).get("iso_code") or ""
        return ISO_TO_COUNTRY.get(iso, DEFAULT_COUNTRY)
    except Exception:
        # قاعدة مفقودة/معطوبة ⟵ الافتراضي الآمن، ولا نكسر التسجيل أبدًا
        return DEFAULT_COUNTRY
