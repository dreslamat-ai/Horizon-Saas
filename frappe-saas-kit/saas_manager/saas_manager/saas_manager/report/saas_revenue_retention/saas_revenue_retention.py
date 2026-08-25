"""
Subscription revenue and retention.

What this report is for: telling the difference between growth and churn
masked by growth. Headline MRR can rise for months while retention rots
underneath, so every view here pairs a revenue number with a survival number.

Definitions used (stated explicitly, because every SaaS dashboard defines
these differently and a silent definition is a wrong number waiting to happen):

  MRR        sum of the monthly price of tenants that are Active AND past
             their trial. Trials contribute 0 — they haven't paid anything.
  Committed  MRR + the monthly value of tenants still in trial. Useful as a
             ceiling, never as revenue.
  Churn      tenants that moved to Suspended/Cancelled within the period,
             over the tenants that were live at the start of it. A tenant
             that never converted from trial is NOT churn — it's a failed
             conversion, counted separately.
  Collected  the value of SaaS Invoices actually marked Paid in the period.
             This is the only figure here backed by money that moved.
"""

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, nowdate

LIVE = ("Active",)
GONE = ("Suspended", "Cancelled")


def execute(filters=None):
    filters = frappe._dict(filters or {})
    frm = getdate(filters.get("from_date") or add_months(nowdate(), -12))
    to = getdate(filters.get("to_date") or nowdate())

    tenants = _tenants(filters)
    invoices = _invoices(frm, to, filters)

    view = filters.get("group_by") or "Plan"
    if view == "Month":
        data, label = _by_month(tenants, invoices, frm, to), _("الشهر")
    elif view == "Status":
        data, label = _by_status(tenants), _("الحالة")
    else:
        data, label = _by_plan(tenants, invoices), _("الباقة")

    return _columns(label, view), data, None, _chart(data, label), _summary(tenants, invoices, frm, to)


# ------------------------------------------------------------------ #
# data
# ------------------------------------------------------------------ #

def _tenants(filters):
    cond, values = ["1=1"], {}
    if filters.get("plan"):
        cond.append("t.plan = %(plan)s")
        values["plan"] = filters.plan

    return frappe.db.sql(
        f"""SELECT t.name, t.plan, t.status, t.creation,
                   t.trial_ends_on, t.subscription_ends_on,
                   p.monthly_price, p.currency
            FROM `tabTenant Site` t
            LEFT JOIN `tabSaaS Plan` p ON p.name = t.plan
            WHERE {' AND '.join(cond)}""",
        values, as_dict=True,
    )


def _invoices(frm, to, filters):
    cond = ["i.status = 'Paid'", "i.paid_on BETWEEN %(frm)s AND %(to)s"]
    values = {"frm": frm, "to": to}
    if filters.get("plan"):
        cond.append("i.plan = %(plan)s")
        values["plan"] = filters.plan

    return frappe.db.sql(
        f"""SELECT i.name, i.plan, i.amount, i.months, i.paid_on, i.tenant_site
            FROM `tabSaaS Invoice` i
            WHERE {' AND '.join(cond)}""",
        values, as_dict=True,
    )


# ------------------------------------------------------------------ #
# classification
# ------------------------------------------------------------------ #

def _is_trialing(t, on=None):
    """A tenant is trialing while it is live and its trial end date is ahead."""
    if t.status not in LIVE:
        return False
    end = t.get("trial_ends_on")
    return bool(end) and getdate(end) >= getdate(on or nowdate())


def _paying(t):
    return t.status in LIVE and not _is_trialing(t)


def _never_converted(t) -> bool:
    """A tenant that ended while still on its trial window never paid us
    anything, so counting it as churn would overstate churn and understate
    the real problem, which is trial conversion. lifecycle.activate() always
    pushes subscription_ends_on past trial_ends_on, so equality (or a missing
    subscription date) means the trial simply lapsed."""
    if t.status not in GONE:
        return False
    trial, sub = t.get("trial_ends_on"), t.get("subscription_ends_on")
    if not trial:
        return False
    return (not sub) or getdate(sub) <= getdate(trial)


def _churned(t) -> bool:
    return t.status in GONE and not _never_converted(t)


def _blank(key):
    return {"grp": key, "tenants": 0, "paying": 0, "trialing": 0, "churned": 0,
            "lapsed": 0, "mrr": 0.0, "committed": 0.0, "collected": 0.0}


def _finish(buckets):
    out = []
    for b in buckets.values():
        if not (b["tenants"] or b["collected"]):
            continue
        base = b["paying"] + b["churned"]
        b["retention"] = (b["paying"] / base * 100) if base else 0.0
        b["arpu"] = (b["mrr"] / b["paying"]) if b["paying"] else 0.0
        out.append(b)
    return sorted(out, key=lambda x: -x["mrr"])


def _by_plan(tenants, invoices):
    buckets = {}
    for t in tenants:
        key = t.plan or _("بدون باقة")
        b = buckets.setdefault(key, _blank(key))
        b["tenants"] += 1
        price = flt(t.monthly_price)
        if _is_trialing(t):
            b["trialing"] += 1
            b["committed"] += price
        elif _paying(t):
            b["paying"] += 1
            b["mrr"] += price
            b["committed"] += price
        elif _churned(t):
            b["churned"] += 1
        elif _never_converted(t):
            b["lapsed"] += 1
    for inv in invoices:
        key = inv.plan or _("بدون باقة")
        buckets.setdefault(key, _blank(key))["collected"] += flt(inv.amount)
    return _finish(buckets)


def _by_status(tenants):
    buckets = {}
    for t in tenants:
        key = t.status or _("غير محدد")
        b = buckets.setdefault(key, _blank(key))
        b["tenants"] += 1
        price = flt(t.monthly_price)
        if _is_trialing(t):
            b["trialing"] += 1
            b["committed"] += price
        elif _paying(t):
            b["paying"] += 1
            b["mrr"] += price
            b["committed"] += price
        elif _churned(t):
            b["churned"] += 1
        elif _never_converted(t):
            b["lapsed"] += 1
    return _finish(buckets)


def _by_month(tenants, invoices, frm, to):
    """Signup cohorts: how many joined each month, and how many are still live."""
    buckets = {}
    for t in tenants:
        created = getdate(t.creation)
        if not (frm <= created <= to):
            continue
        key = created.strftime("%Y-%m")
        b = buckets.setdefault(key, _blank(key))
        b["tenants"] += 1
        price = flt(t.monthly_price)
        if _is_trialing(t):
            b["trialing"] += 1
            b["committed"] += price
        elif _paying(t):
            b["paying"] += 1
            b["mrr"] += price
            b["committed"] += price
        elif _churned(t):
            b["churned"] += 1
        elif _never_converted(t):
            b["lapsed"] += 1
    for inv in invoices:
        key = getdate(inv.paid_on).strftime("%Y-%m")
        buckets.setdefault(key, _blank(key))["collected"] += flt(inv.amount)

    rows = _finish(buckets)
    return sorted(rows, key=lambda x: x["grp"])


# ------------------------------------------------------------------ #
# presentation
# ------------------------------------------------------------------ #

def _columns(label, view):
    cols = [
        {"fieldname": "grp", "label": label, "fieldtype": "Data", "width": 170},
        {"fieldname": "tenants", "label": _("المواقع"), "fieldtype": "Int", "width": 95},
        {"fieldname": "paying", "label": _("مدفوع"), "fieldtype": "Int", "width": 90},
        {"fieldname": "trialing", "label": _("تجريبي"), "fieldtype": "Int", "width": 90},
        {"fieldname": "churned", "label": _("متوقف"), "fieldtype": "Int", "width": 90},
        {"fieldname": "lapsed", "label": _("تجربة لم تتحول"), "fieldtype": "Int", "width": 130},
        {"fieldname": "retention", "label": _("الاستمرار %"), "fieldtype": "Percent", "width": 115},
        {"fieldname": "mrr", "label": _("الإيراد الشهري"), "fieldtype": "Currency", "width": 140},
        {"fieldname": "arpu", "label": _("متوسط الإيراد للعميل"), "fieldtype": "Currency", "width": 165},
        {"fieldname": "collected", "label": _("محصّل فعليًا"), "fieldtype": "Currency", "width": 150},
    ]
    if view != "Month":
        cols.insert(6, {"fieldname": "committed", "label": _("الإيراد المحتمل"),
                        "fieldtype": "Currency", "width": 145})
    return cols


def _chart(data, label):
    return {
        "data": {
            "labels": [d["grp"] for d in data],
            "datasets": [
                {"name": _("الإيراد الشهري"), "values": [round(d["mrr"], 2) for d in data]},
                {"name": _("محصّل فعليًا"), "values": [round(d["collected"], 2) for d in data]},
            ],
        },
        "type": "bar",
        "colors": ["#1D2D44", "#5083BC"],
    }


def _summary(tenants, invoices, frm, to):
    paying = [t for t in tenants if _paying(t)]
    trialing = [t for t in tenants if _is_trialing(t)]
    churned = [t for t in tenants if _churned(t)]
    lapsed = [t for t in tenants if _never_converted(t)]

    mrr = sum(flt(t.monthly_price) for t in paying)
    collected = sum(flt(i.amount) for i in invoices)
    base = len(paying) + len(churned)
    churn_rate = (len(churned) / base * 100) if base else 0.0

    # trial conversion: of everything that ever left trial, how much converted
    left_trial = [t for t in tenants if t.get("trial_ends_on")
                  and getdate(t.trial_ends_on) < getdate(nowdate())]
    converted = [t for t in left_trial if _paying(t)]
    conv = (len(converted) / len(left_trial) * 100) if left_trial else 0.0

    # renewals due within 30 days — the only actionable number on this screen
    soon = [t for t in paying if t.get("subscription_ends_on")
            and 0 <= (getdate(t.subscription_ends_on) - getdate(nowdate())).days <= 30]
    at_risk = sum(flt(t.monthly_price) for t in soon)

    return [
        {"label": _("الإيراد الشهري (MRR)"), "value": mrr, "datatype": "Currency", "indicator": "Blue"},
        {"label": _("الإيراد السنوي (ARR)"), "value": mrr * 12, "datatype": "Currency"},
        {"label": _("مواقع مدفوعة"), "value": len(paying), "datatype": "Int",
         "indicator": "Green" if paying else "Grey"},
        {"label": _("قيد التجربة"), "value": len(trialing), "datatype": "Int", "indicator": "Orange"},
        {"label": _("تحويل التجربة"), "value": conv, "datatype": "Percent",
         "indicator": "Green" if conv >= 25 else "Orange"},
        {"label": _("نسبة التوقف"), "value": churn_rate, "datatype": "Percent",
         "indicator": "Red" if churn_rate > 10 else "Green"},
        {"label": _("تجارب لم تتحول"), "value": len(lapsed), "datatype": "Int",
         "indicator": "Orange" if lapsed else "Grey"},
        {"label": _("محصّل في الفترة"), "value": collected, "datatype": "Currency"},
        {"label": _("تجديدات خلال 30 يوم"), "value": at_risk, "datatype": "Currency",
         "indicator": "Orange" if at_risk else "Grey"},
    ]
