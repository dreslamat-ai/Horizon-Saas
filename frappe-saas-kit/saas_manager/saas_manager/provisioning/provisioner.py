"""
Provisioner: runs bench CLI commands to create/manage tenant sites.

SECURITY MODEL
--------------
- All shell commands run as an argument LIST (never shell=True, never string
  interpolation into a shell), so tenant input can never inject commands.
- Subdomains are validated against a strict regex BEFORE any command runs.
- DB root password is read from the control site's site_config.json
  (key: saas_db_root_password) and passed via CLI flag — it never appears
  in tenant-facing code paths.

REQUIRED site_config.json KEYS ON THE CONTROL SITE
--------------------------------------------------
  "saas_bench_dir":        "/home/frappe/frappe-bench",
  "saas_root_domain":      "almoaser.cloud",
  "saas_db_root_password": "********",
  "saas_reserved_subdomains": ["www", "app", "admin", "mail", "api"]

NOTE: verified against Frappe v16 docs — new-site uses --db-root-password (v16 also adds --db-user/--db-password for non-root DB users)
(`bench new-site --admin-password --db-root-password`). On v14 the DB flag
is `--mariadb-root-password`. Run `bench new-site --help` on the target
bench and adjust ADMIN/DB flag constants if needed — do not assume.
"""

import json
import re
import os
import secrets
import shutil
import string
import subprocess

import frappe
from frappe.utils import now_datetime, add_days, nowdate

SUBDOMAIN_RE = re.compile(r"^[a-z][a-z0-9-]{2,30}$")

# Adjust after checking `bench new-site --help` on the target bench (v14 vs v15)
DB_ROOT_FLAG = "--db-root-password"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def bench_dir() -> str:
    return frappe.conf.get("saas_bench_dir") or "/home/frappe/frappe-bench"


def root_domain() -> str:
    return frappe.conf.get("saas_root_domain") or "horizonerp.cloud"


def full_site_name(subdomain: str) -> str:
    return f"{subdomain}.{root_domain()}"


def validate_subdomain(subdomain: str):
    subdomain = (subdomain or "").strip().lower()
    if not SUBDOMAIN_RE.match(subdomain):
        frappe.throw(
            "Subdomain must be 3-31 chars: lowercase letters, digits, hyphens, "
            "starting with a letter."
        )
    reserved = frappe.conf.get("saas_reserved_subdomains") or [
        "www", "app", "admin", "mail", "api", "erp", "portal", "billing"
    ]
    if subdomain in reserved:
        frappe.throw("This subdomain is reserved.")
    return subdomain


def random_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _log(tenant_name: str, message: str):
    frappe.db.set_value(
        "Tenant Site", tenant_name, "provisioning_log",
        ((frappe.db.get_value("Tenant Site", tenant_name, "provisioning_log") or "")
         + f"\n[{now_datetime()}] {message}").strip(),
        update_modified=False,
    )
    frappe.db.commit()


def bench_bin() -> str:
    # عمال RQ من supervisor بيشتغلوا بـPATH لا يحوي ~/.local/bin —
    # قيس فعليًا: FileNotFoundError: 'bench' أسقط أول تجهيز (٢٤ أغسطس)
    return (
        frappe.conf.get("saas_bench_bin")
        or shutil.which("bench")
        or os.path.expanduser("~/.local/bin/bench")
    )


def run_bench(args: list, tenant_name: str | None = None, timeout: int = 1800):
    """Run a bench command safely (arg list, no shell)."""
    cmd = [bench_bin()] + args
    if tenant_name:
        # redact any password-looking flag values in the log
        redacted = []
        skip_next = False
        for i, a in enumerate(cmd):
            if skip_next:
                redacted.append("*****")
                skip_next = False
                continue
            redacted.append(a)
            if "password" in a:
                skip_next = True
        _log(tenant_name, "RUN: " + " ".join(redacted))

    proc = subprocess.run(
        cmd, cwd=bench_dir(), capture_output=True, text=True, timeout=timeout
    )
    if tenant_name and proc.stdout.strip():
        _log(tenant_name, proc.stdout.strip()[-2000:])
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[-3000:]
        if tenant_name:
            _log(tenant_name, "ERROR: " + err)
        raise RuntimeError(f"bench {' '.join(args[:2])} failed: {err}")
    return proc.stdout




def apply_plan_config(site: str, plan, tenant_name: str | None = None):
    """Write plan name, limits and feature gates into the tenant's site_config.
    Used at provisioning AND at plan change — single source of truth."""
    run_bench(["--site", site, "set-config", "saas_plan", plan.name], tenant_name)
    for key, val in (
        ("saas_max_users", plan.max_users),
        ("saas_max_companies", plan.get("max_companies")),
        ("saas_max_branches", plan.get("max_branches")),
        ("saas_max_space_mb", plan.max_space_mb),
    ):
        run_bench(["--site", site, "set-config", key, str(int(val or 0)), "--parse"],
                  tenant_name)
    feats = plan.features_dict() if hasattr(plan, "features_dict") else {}
    run_bench(["--site", site, "set-config", "saas_features",
               json.dumps(feats), "--parse"], tenant_name)

# --------------------------------------------------------------------------- #
# main provisioning job (runs on the LONG queue)
# --------------------------------------------------------------------------- #

def apply_branding(site: str, tenant_name: str | None = None):
    """هوية Horizon من أول شاشة: اللوجو والأيقونة ملفات لكل موقع على حدة
    (لا تأتي مع الثيم) — بلاغ حقيقي: أول مستأجر ظهر بلوجو ERPNext الخام."""
    src_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "branding")
    dest_dir = os.path.join(bench_dir(), "sites", site, "public", "files")
    for fname in ("horizon-logo1.png", "horizon-icon.png"):
        src = os.path.join(src_dir, fname)
        if os.path.exists(src) and os.path.isdir(dest_dir):
            shutil.copy(src, os.path.join(dest_dir, fname))
    values = {
        "app_name": "Horizon ERP",
        "app_logo": "/files/horizon-logo1.png",
        "banner_image": "/files/horizon-logo1.png",
        "splash_image": "/files/horizon-logo1.png",
        "favicon": "/files/horizon-icon.png",
    }
    run_bench(
        ["--site", site, "execute", "frappe.db.set_value",
         "--args", json.dumps(["Website Settings", "Website Settings", values])],
        tenant_name,
    )
    run_bench(["--site", site, "clear-website-cache"], tenant_name)


def complete_site_setup(site: str, doc, tenant_name: str | None = None):
    """إكمال إعداد ERPNext تلقائياً — العميل يدخل نظاماً جاهزاً بالعربي بلا
    ويزارد. طلب المالك «نختصر كل ده للعملاء» بعد ما عميلاً حقيقياً وقع في
    الويزارد الإنجليزي بخطأ خادم (country=None في تثبيت البريسِتس)."""
    year = nowdate()[:4]
    name = (doc.customer_name or "").strip() or "شركتي"
    words = [w for w in name.split() if w]
    abbr = "".join(w[0] for w in words[:3])[:5] or "HZ"
    args = {
        "language": "العربية",
        "country": "Saudi Arabia",
        "timezone": "Asia/Riyadh",
        "currency": "SAR",
        "company_name": name,
        "company_abbr": abbr,
        # الاختياران المتاحان للسعودية (مقيسان): Standard / Standard with Numbers
        # — المرقمة هي عرف المحاسبة في السوق السعودي
        "chart_of_accounts": "Standard with Numbers",
        "fy_start_date": f"{year}-01-01",
        "fy_end_date": f"{year}-12-31",
        "setup_demo": 0,
        # لا full_name/email هنا: مستخدم المالك اتعمل قبلها بـadd-system-manager،
        # وتمريرهما يخلّي الإعداد يحاول إنشاءه تانياً فيقع بـDuplicateEntryError
        # (حصل فعلاً في أول تجربة دخان)
    }
    run_bench(
        ["--site", site, "execute",
         "frappe.desk.page.setup_wizard.setup_wizard.setup_complete",
         "--kwargs", json.dumps({"args": args}, ensure_ascii=False)],
        tenant_name, timeout=1800,
    )


def provision_site(tenant: str):
    """
    End-to-end provisioning for a Tenant Site document:
      1. bench new-site
      2. install plan apps
      3. write plan metadata into tenant site_config
      4. create the owner user as System Manager
      5. mark Active + set trial end + send welcome email
    """
    doc = frappe.get_doc("Tenant Site", tenant)
    site = doc.site_name
    plan = frappe.get_doc("SaaS Plan", doc.plan)

    doc.db_set("status", "Provisioning")
    frappe.db.commit()

    db_root = frappe.conf.get("saas_db_root_password")
    if not db_root:
        doc.db_set("status", "Failed")
        _log(tenant, "Missing saas_db_root_password in control site config.")
        return

    admin_pwd = random_password()
    owner_pwd = random_password(12)

    try:
        # 1) create site
        run_bench(
            ["new-site", site,
             "--admin-password", admin_pwd,
             DB_ROOT_FLAG, db_root],
            tenant_name=tenant, timeout=2400,
        )

        # 2) install plan apps + horizon_client (limits/features enforcement — always)
        #    + horizon_desk_theme: هوية Horizon لازم تظهر من أول شاشة دخول
        #    (بلاغ حقيقي: أول مستأجر اتبنى بشاشة فرابي الخام)
        for app in plan.apps_list() + ["horizon_client", "horizon_desk_theme"]:
            run_bench(["--site", site, "install-app", app],
                      tenant_name=tenant, timeout=2400)

        # 3) plan metadata + limits + feature gates inside the tenant site config
        apply_plan_config(site, plan, tenant_name=tenant)

        # 3.5) هوية Horizon (لوجو/أيقونة/اسم) — قبل أول دخول للمستخدم
        apply_branding(site, tenant_name=tenant)

        # 4) مستخدم المالك كمدير نظام — **قبل** الإعداد التلقائي، وإلا
        #    الإعداد ينشئه الأول وadd-system-manager يقع بـDuplicateEntryError
        run_bench(
            ["--site", site, "add-system-manager", doc.email,
             "--first-name", doc.customer_name or "Owner",
             "--password", owner_pwd],
            tenant_name=tenant,
        )

        # 4.5) إعداد كامل تلقائي: شركة العميل + عربي + السعودية — بلا ويزارد
        complete_site_setup(site, doc, tenant_name=tenant)

        # 5) activate trial
        trial_end = add_days(nowdate(), plan.trial_days or 14)
        doc.db_set("status", "Active")
        doc.db_set("provisioned_on", now_datetime())
        doc.db_set("trial_ends_on", trial_end)
        doc.db_set("subscription_ends_on", trial_end)
        frappe.db.commit()
        run_bench(["--site", site, "set-config", "saas_subscription_ends_on",
                   str(trial_end)], tenant_name=tenant)

        _send_welcome_email(doc, owner_pwd)
        _log(tenant, "Provisioning completed successfully.")

    except Exception:
        doc.db_set("status", "Failed")
        frappe.db.commit()
        frappe.log_error(frappe.get_traceback(), f"Provisioning failed: {site}")
        raise


def _send_welcome_email(doc, owner_pwd: str):
    url = f"https://{doc.site_name}"
    frappe.sendmail(
        recipients=[doc.email],
        subject="نظامك جاهز ✅ | Horizon ERP",
        message=f"""
        <div dir="rtl" style="font-family:Cairo,Arial,sans-serif;color:#221f1f">
          <h2 style="color:#1D2D44">أهلاً {frappe.utils.escape_html(doc.customer_name or '')} 👋</h2>
          <p>أنا <b>الاء</b>، وكيلك الذكي في هورايزون — خلّصت تجهيز نظامك وهو جاهز على الرابط التالي:</p>
          <p><a href="{url}" style="color:#1D2D44;font-weight:bold">{url}</a></p>
          <p>بيانات الدخول:</p>
          <ul>
            <li>البريد: {doc.email}</li>
            <li>كلمة المرور المؤقتة: <b>{owner_pwd}</b></li>
          </ul>
          <p>من فضلك غيّر كلمة المرور بعد أول تسجيل دخول.</p>
          <p>الفترة التجريبية تنتهي في: <b>{doc.trial_ends_on}</b></p>
          <p style="color:#5083BC;font-weight:bold">— الاء | Horizon Smart Systems</p>
        </div>
        """,
        delayed=False,
    )
