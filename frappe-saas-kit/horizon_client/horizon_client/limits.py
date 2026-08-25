"""
Plan limit enforcement inside the tenant site.

All limits are read from the tenant's site_config.json (frappe.conf), which is
written exclusively by the Horizon control plane via `bench set-config`.
Convention: 0 or missing = unlimited.

Keys:
    saas_max_users      int
    saas_max_companies  int
    saas_max_branches   int
    saas_features       dict  e.g. {"advanced_reports": 1, "api_access": 0}
    saas_plan           str
"""

import frappe
from frappe import _
from frappe.utils import cint

UPGRADE_HINT = _("للترقية لباقة أعلى تواصل مع Horizon أو اضغط «ترقية الباقة».")


def _limit(key: str) -> int:
    return cint(frappe.conf.get(key) or 0)


# ------------------------------------------------------------------ #
# limits
# ------------------------------------------------------------------ #

def check_user_limit(doc, method=None):
    limit = _limit("saas_max_users")
    if not limit:
        return
    # only enabled System Users count toward the seat limit
    if doc.get("user_type") != "System User" or not cint(doc.get("enabled")):
        return
    current = frappe.db.count("User", {
        "user_type": "System User",
        "enabled": 1,
        "name": ["not in", ["Administrator", "Guest", doc.name]],
    })
    if current + 1 > limit:
        frappe.throw(
            _("باقتك ({0}) تسمح بـ {1} مستخدم نشط كحد أقصى. {2}").format(
                frappe.conf.get("saas_plan") or "Horizon", limit, UPGRADE_HINT
            ),
            title=_("تم الوصول لحد المستخدمين"),
        )


def check_company_limit(doc, method=None):
    _check_count("Company", "saas_max_companies", doc,
                 _("باقتك ({0}) تسمح بـ {1} شركة كحد أقصى. {2}"),
                 _("تم الوصول لحد الشركات"))


def check_branch_limit(doc, method=None):
    _check_count("Branch", "saas_max_branches", doc,
                 _("باقتك ({0}) تسمح بـ {1} فرع كحد أقصى. {2}"),
                 _("تم الوصول لحد الفروع"))


def _check_count(doctype, key, doc, msg, title):
    limit = _limit(key)
    if not limit:
        return
    current = frappe.db.count(doctype, {"name": ["!=", doc.name]})
    if current + 1 > limit:
        frappe.throw(
            msg.format(frappe.conf.get("saas_plan") or "Horizon", limit, UPGRADE_HINT),
            title=title,
        )


# ------------------------------------------------------------------ #
# feature gates
# ------------------------------------------------------------------ #

# خاصية الباقة ⟵ موديولات فرابي اللي بتتقفل لما قيمتها 0.
# قرار المالك (٢٥ أغسطس): الحسابات من الاحترافية، وHR/التصنيع/المشاريع
# مع باقة أعمال فقط — الأولى تشغيل يومي (مخازن/مبيعات/مشتريات).
GATED_MODULES = {
    "accounting": ["Accounts"],
    "hr": ["HR", "Payroll"],
    "manufacturing": ["Manufacturing"],
    "projects": ["Projects"],
}


def sync_module_blocks(doc, method=None):
    """بوابة الموديولات حسب الباقة — block_modules الأصيلة في فرابي.

    بتتطبق مع كل حفظ لمستخدم (الإنشاء والتعديل): المفتاح الموجود في
    saas_features بقيمة 0 يقفل موديولاته، والمفتاح الغايب (مواقع قديمة
    قبل هيكل الباقات، أو غير مُدارة) = لا قفل — لا نكسر موقعًا قائمًا.
    وإعادة التطبيق في كل validate بتمنع مدير النظام عند العميل من شيل
    القفل يدويًا من شاشة المستخدم — بيرجع مع أول حفظ.
    """
    feats = frappe.conf.get("saas_features") or {}
    if not feats or doc.name in ("Administrator", "Guest"):
        return
    blocked = []
    for key, modules in GATED_MODULES.items():
        if key in feats and not cint(feats.get(key)):
            blocked += [m for m in modules if frappe.db.exists("Module Def", m)]
    existing = {d.module for d in (doc.get("block_modules") or [])}
    for m in blocked:
        if m not in existing:
            doc.append("block_modules", {"module": m})


def enforce_currency(doc, method=None):
    """عملة الموقع مثبتة من بلد الاشتراك (saas_currency في site_config).

    طلب المالك (٢٥ أغسطس): «العميل مايقدرش يغير العملة من داخل النظام
    لمنع التلاعب» — تسعيره مربوط ببلده المكتشف من الـIP وقت التسجيل.
    غياب المفتاح (مواقع قديمة غير مُدارة) = لا قفل، لا نكسر موقعًا قائمًا.
    """
    locked = frappe.conf.get("saas_currency")
    if not locked:
        return
    val = doc.get("default_currency")
    if val and val != locked:
        frappe.throw(
            _("عملة نظامك مثبتة على {0} حسب بلد اشتراكك ولا يمكن تغييرها من داخل النظام. لو محتاج تغييرها فعلاً تواصل مع دعم Horizon.").format(locked),
            title=_("العملة مقفولة"),
        )


def has_feature(key: str) -> bool:
    """Use anywhere in server code: from horizon_client.limits import has_feature"""
    feats = frappe.conf.get("saas_features") or {}
    return bool(cint(feats.get(key) or 0))


def require_feature(key: str, label: str | None = None):
    """Guard an endpoint/report: raises if the plan doesn't include the feature."""
    if not has_feature(key):
        frappe.throw(
            _("هذه الخاصية ({0}) غير متاحة في باقتك الحالية. {1}").format(
                label or key, UPGRADE_HINT
            ),
            title=_("خاصية غير مفعّلة"),
        )
