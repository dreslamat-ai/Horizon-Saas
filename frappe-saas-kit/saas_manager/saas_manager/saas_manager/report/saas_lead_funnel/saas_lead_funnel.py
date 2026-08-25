"""
Lead funnel — where calculator traffic turns into customers.

Design note: this report answers three questions a sales lead actually asks,
in one screen:
  1. how many leads, and what did they say they're losing?
  2. which segment converts better — plants or contractors?
  3. are high-estimate leads converting better than low ones? (i.e. is the
     calculator attracting the right people, or just curious browsers?)

Question 3 is the one that decides whether the calculator is worth keeping,
so it gets its own band breakdown rather than a single average.
"""

import frappe
from frappe import _
from frappe.utils import flt

STATUSES = ["New", "Contacted", "Qualified", "Converted", "Dropped"]
WON = "Converted"
LOST = "Dropped"

# estimate bands in SAR — chosen to separate "curious" from "has a real problem"
BANDS = [
    (0, 250_000, "أقل من 250 ألف"),
    (250_000, 1_000_000, "250 ألف – مليون"),
    (1_000_000, 3_000_000, "مليون – 3 مليون"),
    (3_000_000, float("inf"), "أكثر من 3 مليون"),
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    rows = _fetch(filters)

    group_by = filters.get("group_by") or "Segment"
    if group_by == "Estimate Band":
        data = _by_band(rows)
        label = _("شريحة التقدير")
    elif group_by == "Status":
        data = _by_status(rows)
        label = _("الحالة")
    else:
        data = _by_segment(rows)
        label = _("القطاع")

    return _columns(label), data, None, _chart(data, label), _summary(rows)


# ------------------------------------------------------------------ #

def _fetch(filters):
    cond, values = ["1=1"], {}
    if filters.get("from_date"):
        cond.append("l.creation >= %(from_date)s")
        values["from_date"] = filters.from_date
    if filters.get("to_date"):
        cond.append("l.creation <= %(to_date)s")
        values["to_date"] = filters.to_date
    if filters.get("source"):
        cond.append("l.source = %(source)s")
        values["source"] = filters.source
    if filters.get("segment"):
        cond.append("l.calc_mode = %(segment)s")
        values["segment"] = filters.segment

    return frappe.db.sql(
        f"""SELECT l.name, l.calc_mode, l.status, l.estimate, l.company, l.creation
            FROM `tabSaaS Lead` l
            WHERE {' AND '.join(cond)}""",
        values, as_dict=True,
    )


def _blank(key):
    return {
        "grp": key, "leads": 0, "total_estimate": 0.0,
        "contacted": 0, "qualified": 0, "converted": 0, "dropped": 0,
    }


def _tally(bucket, r):
    bucket["leads"] += 1
    bucket["total_estimate"] += flt(r.estimate)
    st = r.status or "New"
    # the funnel is cumulative: a Converted lead was necessarily contacted
    if st in ("Contacted", "Qualified", "Converted"):
        bucket["contacted"] += 1
    if st in ("Qualified", "Converted"):
        bucket["qualified"] += 1
    if st == WON:
        bucket["converted"] += 1
    if st == LOST:
        bucket["dropped"] += 1


def _finish(buckets):
    out = []
    for b in buckets.values():
        if not b["leads"]:
            continue
        b["avg_estimate"] = b["total_estimate"] / b["leads"]
        b["conversion"] = b["converted"] / b["leads"] * 100
        out.append(b)
    return sorted(out, key=lambda x: -x["leads"])


def _by_segment(rows):
    buckets = {}
    for r in rows:
        key = r.calc_mode or _("غير محدد")
        buckets.setdefault(key, _blank(key))
        _tally(buckets[key], r)
    return _finish(buckets)


def _by_status(rows):
    buckets = {s: _blank(s) for s in STATUSES}
    for r in rows:
        _tally(buckets.setdefault(r.status or "New", _blank(r.status or "New")), r)
    return [b for b in (dict(x, avg_estimate=(x["total_estimate"] / x["leads"] if x["leads"] else 0),
                             conversion=(x["converted"] / x["leads"] * 100 if x["leads"] else 0))
                        for x in buckets.values()) if b["leads"]]


def _by_band(rows):
    buckets = {label: _blank(label) for _lo, _hi, label in BANDS}
    for r in rows:
        est = flt(r.estimate)
        for lo, hi, label in BANDS:
            if lo <= est < hi:
                _tally(buckets[label], r)
                break
    ordered = [buckets[label] for _lo, _hi, label in BANDS if buckets[label]["leads"]]
    for b in ordered:
        b["avg_estimate"] = b["total_estimate"] / b["leads"]
        b["conversion"] = b["converted"] / b["leads"] * 100
    return ordered


# ------------------------------------------------------------------ #

def _columns(label):
    return [
        {"fieldname": "grp", "label": label, "fieldtype": "Data", "width": 190},
        {"fieldname": "leads", "label": _("عدد الليدز"), "fieldtype": "Int", "width": 100},
        {"fieldname": "contacted", "label": _("تم التواصل"), "fieldtype": "Int", "width": 110},
        {"fieldname": "qualified", "label": _("مؤهل"), "fieldtype": "Int", "width": 90},
        {"fieldname": "converted", "label": _("تحوّل"), "fieldtype": "Int", "width": 90},
        {"fieldname": "dropped", "label": _("مستبعد"), "fieldtype": "Int", "width": 90},
        {"fieldname": "conversion", "label": _("نسبة التحويل %"), "fieldtype": "Percent", "width": 130},
        {"fieldname": "avg_estimate", "label": _("متوسط التقدير"), "fieldtype": "Currency", "width": 150},
        {"fieldname": "total_estimate", "label": _("إجمالي التقديرات"), "fieldtype": "Currency", "width": 160},
    ]


def _chart(data, label):
    return {
        "data": {
            "labels": [d["grp"] for d in data],
            "datasets": [
                {"name": _("ليدز"), "values": [d["leads"] for d in data]},
                {"name": _("تحوّل"), "values": [d["converted"] for d in data]},
            ],
        },
        "type": "bar",
        "colors": ["#1D2D44", "#5083BC"],   # navy for volume, blue only for wins
        "barOptions": {"stacked": False},
    }


def _summary(rows):
    total = len(rows)
    won = sum(1 for r in rows if r.status == WON)
    pipeline = sum(flt(r.estimate) for r in rows if r.status not in (WON, LOST))
    avg = (sum(flt(r.estimate) for r in rows) / total) if total else 0
    conv = (won / total * 100) if total else 0

    return [
        {"label": _("إجمالي الليدز"), "value": total, "datatype": "Int", "indicator": "Blue"},
        {"label": _("تحوّلوا لعملاء"), "value": won, "datatype": "Int",
         "indicator": "Green" if won else "Grey"},
        {"label": _("نسبة التحويل"), "value": conv, "datatype": "Percent",
         "indicator": "Green" if conv >= 10 else "Orange"},
        {"label": _("متوسط التقدير المُعلن"), "value": avg, "datatype": "Currency"},
        {"label": _("تقديرات قيد المتابعة"), "value": pipeline, "datatype": "Currency",
         "indicator": "Orange"},
    ]
