"""KushLife: the check done on every visit, its trend and its early-warning flags.

Each visit's report holds ``report["kushlife"]``::

    {"version": 1,
     "checks": {"safe": {"status": "ok"|"concern", "chips": [...], "note": ""}, ...4 checks},
     "sleep": "well"|"poorly"|"unsure", "appetite": "usual"|"less"|"more",
     "vitals": {"bp_sys": 130, "bp_dia": 85, "spo2": 97, "sugar": 140}}

and ``report["checks"]`` keeps the plain ok/concern per check (older readers use it).

Flags are worked out from the recent visits each time (no table): amber goes to the care
manager; red also tells the family that the care manager will call within 2 hours.
A manager acknowledging a flag is stored on the client (``custom_attributes.kushlife_ack``).
This is care observation, not diagnosis: no disease words anywhere.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.responses import raise_bad_request
from app.models.care_job import CareJob
from app.models.elder import Elder

CHECKS = ("safe", "steady", "settled", "connected")
LABELS = {"safe": "Safe", "steady": "Steady", "settled": "Settled", "connected": "Connected"}
HINTS = {
    "safe": "Home and person safe today",
    "steady": "Moving as usual, no falls",
    "settled": "Mood, eating, sleep as usual",
    "connected": "In touch with people, anything to tell the family",
}
CHIPS = {
    "safe": {
        "new_hazard": "New hazard at home",
        "meds_missed": "Medicines missed",
        "meds_unsure": "Not sure medicines were taken",
        "stove_gas": "Stove / gas left on",
        "doors_locks": "Doors or locks unsafe",
        "poor_lighting": "Poor lighting",
        "footwear": "Unsafe footwear",
    },
    "steady": {
        "fall": "Had a fall",
        "near_fall": "Nearly fell",
        "unsteady": "Unsteady walking",
        "fear_of_falling": "Afraid of falling",
        "aid_not_used": "Walking aid not used",
    },
    "settled": {
        "ate_less": "Ate less",
        "drank_less": "Drank less",
        "poor_sleep": "Slept poorly",
        "low_mood": "Low mood",
        "confused": "More confused than usual",
        "pain": "In pain",
        "continence": "Continence change",
        "skin": "Skin or wound concern",
        "breathing": "Breathing different",
    },
    "connected": {
        "lonely": "Seemed lonely",
        "no_visitors": "No visitors or calls",
        "message_family": "Has a message for family",
    },
}
SLEEP = ("well", "poorly", "unsure")
APPETITE = ("usual", "less", "more")
MOOD = ("good", "low")  # not asked separately: "low" when the Settled check has the low-mood chip
# Chips that always make the visit red: decision support, not diagnosis.
RED_CHIPS = {"fall", "confused", "breathing"}


def _int(v, lo: int, hi: int) -> int | None:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


def build_record(data: dict) -> dict:
    """Validate a KushLife capture from the visit form. Every check must be answered."""
    raw = data.get("kushlife") if isinstance(data.get("kushlife"), dict) else None
    if raw is None:
        # Older clients sent {"checks": {...}}: accepted only when all four are answered.
        legacy = data.get("checks") if isinstance(data.get("checks"), dict) else {}
        if not _complete_legacy(legacy):
            raise_bad_request("Answer all four KushLife checks (Safe, Steady, Settled, Connected)")
        raw = {"checks": {k: {"status": legacy[k]} for k in CHECKS}}
    checks_in = raw.get("checks") or {}
    checks: dict[str, dict] = {}
    for k in CHECKS:
        c = checks_in.get(k) or {}
        status = c.get("status")
        if status not in ("ok", "concern"):
            raise_bad_request(f"Answer the {LABELS[k]} check: same as usual, or changed")
        chips = [x for x in (c.get("chips") or []) if x in CHIPS[k]][:10]
        checks[k] = {"status": status, "chips": chips if status == "concern" else [], "note": str(c.get("note") or "").strip()[:300]}
    sleep = raw.get("sleep") if raw.get("sleep") in SLEEP else None
    appetite = raw.get("appetite") if raw.get("appetite") in APPETITE else None
    vin = raw.get("vitals") or {}
    vitals = {
        k: v
        for k, v in {
            "bp_sys": _int(vin.get("bp_sys"), 60, 260),
            "bp_dia": _int(vin.get("bp_dia"), 30, 160),
            "spo2": _int(vin.get("spo2"), 50, 100),
            "pulse": _int(vin.get("pulse"), 30, 220),
            "sugar": _int(vin.get("sugar"), 20, 600),
        }.items()
        if v is not None
    }
    rec = {"version": 1, "checks": checks, "sleep": sleep, "appetite": appetite, "vitals": vitals}
    if raw.get("mood") in MOOD:
        rec["mood"] = raw["mood"]
    return rec


def _complete_legacy(checks: dict) -> bool:
    return isinstance(checks, dict) and all(checks.get(k) in ("ok", "concern") for k in CHECKS)


def plain_checks(record: dict) -> dict:
    return {k: record["checks"][k]["status"] for k in CHECKS}


def visit_level(record: dict, baseline: dict | None = None) -> tuple[str, list[str]]:
    """Level for one visit on its own: red / amber / ok, with plain reasons.

    Readings are compared with the client's "Normal for" baseline when there is one
    (a person whose oxygen is usually 90% is not red at 90%); otherwise wide generic limits.
    """
    reasons: list[str] = []
    level = "ok"
    b = baseline or {}
    chips = {c for k in CHECKS for c in record["checks"][k]["chips"]}
    concerns = [k for k in CHECKS if record["checks"][k]["status"] == "concern"]
    if chips & RED_CHIPS:
        level = "red"
        reasons += [CHIPS_FLAT[c] for c in sorted(chips & RED_CHIPS)]
    vit = record.get("vitals") or {}
    spo2 = vit.get("spo2")
    if spo2 is not None:
        base = b.get("spo2")
        low = (spo2 < SPO2_FLOOR or spo2 <= base - SPO2_DROP) if base else spo2 < SPO2_GENERIC
        if low:
            level = "red"
            reasons.append(f"Oxygen level {spo2}%" + (f" (usually {base}%)" if base else ""))
    if len(concerns) >= 3:
        level = "red"
        reasons.append(f"{len(concerns)} of 4 checks changed")
    amber: list[str] = []
    if "safe" in concerns:
        amber.append("Safe check changed")
    amber += _reading_changes(vit, b)
    if amber:
        reasons += amber
        if level != "red":
            level = "amber"
    return level, reasons


# Reading limits. With a baseline: change from the client's own normal; without: wide generic limits.
SPO2_GENERIC = 92
SPO2_FLOOR = 85
SPO2_DROP = 4
BP_SYS_GENERIC = (90, 180)
BP_DIA_GENERIC = (50, 110)
BP_SYS_SHIFT = 25
BP_DIA_SHIFT = 15
PULSE_GENERIC = (50, 110)
PULSE_SHIFT = 20


def _reading_changes(vit: dict, b: dict) -> list[str]:
    out: list[str] = []
    sys_, dia = vit.get("bp_sys"), vit.get("bp_dia")
    bs, bd = b.get("bp_sys"), b.get("bp_dia")
    off = False
    if sys_ is not None:
        off |= abs(sys_ - bs) >= BP_SYS_SHIFT if bs else not BP_SYS_GENERIC[0] <= sys_ < BP_SYS_GENERIC[1]
    if dia is not None:
        off |= abs(dia - bd) >= BP_DIA_SHIFT if bd else not BP_DIA_GENERIC[0] <= dia < BP_DIA_GENERIC[1]
    if off:
        bp = f"{sys_ if sys_ is not None else '–'}/{dia if dia is not None else '–'}"
        out.append(f"BP {bp}" + (f" (usually {bs}/{bd})" if bs and bd else ""))
    pulse, bpu = vit.get("pulse"), b.get("pulse")
    if pulse is not None:
        if (abs(pulse - bpu) >= PULSE_SHIFT) if bpu else not PULSE_GENERIC[0] <= pulse <= PULSE_GENERIC[1]:
            out.append(f"Pulse {pulse}" + (f" (usually {bpu})" if bpu else ""))
    return out


# --- "Normal for Amma": the client's own baseline -------------------------------

BASELINE_KEY = "kushlife_baseline"
BASELINE_VISITS = 10  # last N visits with KushLife
BASELINE_MIN = 3  # readings needed before there is a baseline
NUMERIC = ("bp_sys", "bp_dia", "spo2", "pulse")
NUMERIC_RANGE = {"bp_sys": (60, 260), "bp_dia": (30, 160), "spo2": (50, 100), "pulse": (30, 220)}
CATEGORICAL = {"sleep": SLEEP[:2], "appetite": APPETITE, "mood": MOOD}
BASELINE_KEYS = NUMERIC + tuple(CATEGORICAL)


def visit_mood(rec: dict) -> str | None:
    if rec.get("mood") in MOOD:
        return rec["mood"]
    checks = rec.get("checks") or {}
    if not isinstance(checks.get("settled"), dict):
        return None
    return "low" if "low_mood" in (checks["settled"].get("chips") or []) else "good"


def _quantile(xs: list[float], q: float) -> float:
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def robust_median(values) -> int | None:
    """Median after dropping outliers (outside 1.5 x IQR); None with fewer than BASELINE_MIN readings."""
    xs = sorted(float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
    if len(xs) < BASELINE_MIN:
        return None
    if len(xs) >= 4:
        q1, q3 = _quantile(xs, 0.25), _quantile(xs, 0.75)
        spread = 1.5 * (q3 - q1)
        kept = [x for x in xs if q1 - spread <= x <= q3 + spread]
        xs = kept or xs
    return int(round(_quantile(xs, 0.5)))


def usual_answer(values, allowed: tuple) -> str | None:
    """Most common answer (ties go to the first in ``allowed``, the 'as usual' one)."""
    vals = [v for v in values if v in allowed]
    if len(vals) < BASELINE_MIN:
        return None
    return max(allowed, key=lambda a: (vals.count(a), -allowed.index(a)))


def computed_baseline(records: list[dict]) -> dict:
    recs = records[:BASELINE_VISITS]
    out: dict = {k: robust_median((r.get("vitals") or {}).get(k) for r in recs) for k in NUMERIC}
    out["sleep"] = usual_answer([r.get("sleep") for r in recs], CATEGORICAL["sleep"])
    out["appetite"] = usual_answer([r.get("appetite") for r in recs], CATEGORICAL["appetite"])
    out["mood"] = usual_answer([visit_mood(r) for r in recs], CATEGORICAL["mood"])
    return out


def _override(elder: Elder | None) -> dict:
    attrs = elder.custom_attributes if elder is not None and isinstance(elder.custom_attributes, dict) else {}
    return dict(attrs.get(BASELINE_KEY) or {})


def baseline_for(db: Session, elder: Elder, records: list[dict] | None = None) -> dict:
    """The client's normal: staff override per item, else computed from the last visits."""
    if records is None:
        records = [rec for _j, rec in _records(db, elder.id, BASELINE_VISITS)]
    computed = computed_baseline(records)
    ov = _override(elder)
    values, source = {}, {}
    for k in BASELINE_KEYS:
        if ov.get(k) is not None:
            values[k], source[k] = ov[k], "override"
        else:
            values[k], source[k] = computed.get(k), ("visits" if computed.get(k) is not None else None)
    return {
        "values": values,
        "computed": computed,
        "source": source,
        "visits_used": min(len(records), BASELINE_VISITS),
        "override_by": ov.get("by"),
        "override_at": ov.get("at"),
        "label": f"Normal for {(elder.first_name or '').strip() or 'them'}",
    }


def set_baseline_override(db: Session, elder: Elder, body: dict, user) -> dict:
    """Staff set (or clear with null) any of the baseline items; the rest stay computed."""
    db.refresh(elder)
    attrs = dict(elder.custom_attributes or {})
    ov = {k: v for k, v in dict(attrs.get(BASELINE_KEY) or {}).items() if k in BASELINE_KEYS}
    for k in BASELINE_KEYS:
        if k not in body:
            continue
        v = body[k]
        if v is None or v == "":
            ov.pop(k, None)
        elif k in NUMERIC:
            lo, hi = NUMERIC_RANGE[k]
            n = _int(v, lo, hi)
            if n is None:
                raise_bad_request(f"{k} must be between {lo} and {hi}")
            ov[k] = n
        else:
            if v not in CATEGORICAL[k]:
                raise_bad_request(f"{k} must be one of {', '.join(CATEGORICAL[k])}")
            ov[k] = v
    if ov:
        who = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        ov.update({"by": who, "at": datetime.now(timezone.utc).isoformat()})
        attrs[BASELINE_KEY] = ov
    else:
        attrs.pop(BASELINE_KEY, None)
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    return baseline_for(db, elder)


CHIPS_FLAT = {c: label for k in CHIPS for c, label in CHIPS[k].items()}


# --- Reading the visits ----------------------------------------------------------


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _records(db: Session, elder_id: int, limit: int) -> list[tuple[CareJob, dict]]:
    """(job, KushLife record) for completed visits, newest first."""
    rows = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder_id, CareJob.status == "completed", CareJob.kind.in_(("visit", "install")))
        .order_by(CareJob.completed_at.desc().nullslast(), CareJob.id.desc())
        .limit(limit * 3)
        .all()
    )
    out: list[tuple[CareJob, dict]] = []
    for j in rows:
        rep = j.report or {}
        rec = rep.get("kushlife")
        if not rec and _complete_legacy(rep.get("checks")):
            # Visits saved before KushLife v1: four ok/concern answers, no chips.
            rec = {"checks": {k: {"status": rep["checks"][k], "chips": [], "note": ""} for k in CHECKS}}
        if not rec or not isinstance(rec.get("checks"), dict):
            continue
        out.append((j, rec))
        if len(out) >= limit:
            break
    return out


def recent_visits(db: Session, elder_id: int, limit: int = 12, baseline: dict | None = None) -> list[dict]:
    """Completed visits that have a KushLife check, newest first. Levels use the client's
    "Normal for" baseline (worked out here when not passed in)."""
    pairs = _records(db, elder_id, max(limit, BASELINE_VISITS))
    if baseline is None:
        elder = db.get(Elder, elder_id)
        baseline = baseline_for(db, elder, [r for _j, r in pairs])["values"] if elder else {}
    out = []
    for j, rec in pairs[:limit]:
        rep = j.report or {}
        when = _aware(j.completed_at or j.scheduled_at)
        level, reasons = visit_level(rec, baseline)
        out.append(
            {
                "job_id": j.id,
                "date": when.isoformat() if when else None,
                "title": j.title,
                "checks": plain_checks(rec),
                "chips": {k: [CHIPS_FLAT.get(c, c) for c in rec["checks"][k]["chips"]] for k in CHECKS},
                "sleep": rec.get("sleep"),
                "appetite": rec.get("appetite"),
                "mood": visit_mood(rec),
                "vitals": rec.get("vitals") or {},
                "note": rep.get("note") or "",
                "level": level,
                "reasons": reasons,
                "photo_count": len(rep.get("photo_ids") or []),
            }
        )
        if len(out) >= limit:
            break
    return out


def _ack(elder: Elder) -> dict:
    attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
    return dict(attrs.get("kushlife_ack") or {})


def open_flags(elder: Elder, visits: list[dict]) -> list[dict]:
    """Flags from the latest visits. Key = rule + latest visit, so a new visit can raise it again."""
    if not visits:
        return []
    latest = visits[0]
    flags: list[dict] = []
    if latest["level"] in ("red", "amber"):
        flags.append(
            {
                "key": f"visit:{latest['job_id']}",
                "level": latest["level"],
                "check": None,
                "reason": "; ".join(latest["reasons"]) or "Something changed on the last visit",
                "job_id": latest["job_id"],
                "date": latest["date"],
            }
        )
    for k in CHECKS:
        run = 0
        for v in visits:
            if v["checks"][k] == "concern":
                run += 1
            else:
                break
        last3 = sum(1 for v in visits[:3] if v["checks"][k] == "concern")
        # Key on the visit where the change began, so the same streak keeps the same key.
        run_start = visits[run - 1]["job_id"] if run else latest["job_id"]
        first_of_three = next((v["job_id"] for v in reversed(visits[:3]) if v["checks"][k] == "concern"), latest["job_id"])
        if run >= 3:
            flags.append({"key": f"{k}:run3:{run_start}", "level": "red", "check": k,
                          "reason": f"{LABELS[k]}: changed on {run} visits in a row", "job_id": latest["job_id"],
                          "date": latest["date"]})
        elif last3 >= 2 and visits[0]["checks"][k] == "concern":
            flags.append({"key": f"{k}:watch:{first_of_three}", "level": "amber", "check": k,
                          "reason": f"{LABELS[k]}: changed on {last3} of the last 3 visits", "job_id": latest["job_id"],
                          "date": latest["date"]})
    acks = _ack(elder)
    for f in flags:
        a = acks.get(f["key"]) or {}
        f["acknowledged_by"] = a.get("by")
        f["acknowledged_at"] = a.get("at")
    # One flag per visit-level and per check; red before amber.
    flags.sort(key=lambda f: (f["level"] != "red", f["key"]))
    return flags


def streaks(visits: list[dict]) -> dict:
    out = {}
    for k in CHECKS:
        n = 0
        for v in visits:
            if v["checks"][k] == "ok":
                n += 1
            else:
                break
        out[k] = n
    return out


def pct_ok_30d(visits: list[dict]) -> int | None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    recent = [v for v in visits if v["date"] and datetime.fromisoformat(v["date"]) >= cutoff]
    total = len(recent) * 4
    if not total:
        return None
    ok = sum(1 for v in recent for k in CHECKS if v["checks"][k] == "ok")
    return round(ok * 100 / total)


def summary_line(visits: list[dict], flags: list[dict], manager_name: str = "") -> str:
    if not visits:
        return "No KushLife checks yet. They start with the first visit."
    who = manager_name or "Your care manager"
    red = next((f for f in flags if f["level"] == "red"), None)
    if red:
        return f"{red['reason']}. {who} will call you within 2 hours."
    amber = next((f for f in flags if f["level"] == "amber"), None)
    if amber:
        return f"{amber['reason']}. {who} is keeping an eye on it."
    noted = reported_changes(visits)
    if noted:
        # No flag, but the carer did report something: say so instead of "as usual".
        return f"Noted on the last visit: {', '.join(noted)}. Nothing that needs action yet."
    s = streaks(visits)
    run = min(s.values())
    if run >= 2:
        return f"All four checks as usual for {run} visits in a row."
    return "All four checks as usual on the last visit."


def reported_changes(visits: list[dict]) -> list[str]:
    """Words the carer ticked on the latest visit ("Slept poorly", "Ate less"), without duplicates."""
    if not visits:
        return []
    v = visits[0]
    out: list[str] = []
    for words in (v.get("chips") or {}).values():
        for w in words or []:
            if w and w not in out:
                out.append(w)
    if v.get("sleep") == "poorly" and "Slept poorly" not in out:
        out.append("Slept poorly")
    if v.get("appetite") == "less" and "Ate less" not in out:
        out.append("Ate less")
    return out


def record_changes(rec: dict | None) -> list[str]:
    """What the carer noted on one saved KushLife record ("Slept poorly", "Ate less").
    Same words as ``reported_changes`` (and so GET /family/status)."""
    if not isinstance(rec, dict):
        return []
    checks = rec.get("checks") if isinstance(rec.get("checks"), dict) else {}
    chips = {
        k: [CHIPS_FLAT.get(c, c) for c in ((checks.get(k) or {}).get("chips") or [])]
        for k in CHECKS
        if isinstance(checks.get(k), dict)
    }
    return reported_changes([{"chips": chips, "sleep": rec.get("sleep"), "appetite": rec.get("appetite")}])


def noted_text(noted: list[str]) -> str:
    """["Slept poorly", "Ate less"] -> "slept poorly, ate less"."""
    return ", ".join(n[:1].lower() + n[1:] for n in noted if n)


def status_word(flags: list[dict], visits: list[dict] | None = None) -> str:
    if any(f["level"] == "red" for f in flags):
        return "We're calling you"
    if any(f["level"] == "amber" for f in flags):
        return "Watching closely"
    if visits and reported_changes(visits):
        return "Small changes noted"
    return "All good"


def kushlife_view(db: Session, elder: Elder, *, limit: int = 8, staff: bool = False) -> dict:
    baseline = baseline_for(db, elder)
    visits = recent_visits(db, elder.id, limit=limit, baseline=baseline["values"])
    flags = open_flags(elder, visits)
    manager = ""
    if elder.manager_user_id:
        from app.models.user import User

        m = db.get(User, elder.manager_user_id)
        manager = (m.first_name or "").strip() if m else ""
    # The family sees red at once, amber once the care manager has seen it (so "keeping an eye
    # on it" is true). Until then an amber change reads as "your care manager has been told".
    shown = flags if staff else [f for f in flags if f["level"] == "red" or f.get("acknowledged_at")]
    line = summary_line(visits, shown, manager)
    if not staff:
        for v in visits:
            if v["level"] == "amber":
                v["level"], v["reasons"] = "ok", []
    # "% as usual" really covers 30 days, not just the visits on the card.
    month = recent_visits(db, elder.id, limit=40, baseline=baseline["values"]) if len(visits) >= limit else visits
    if not staff and len(shown) < len(flags):
        hidden = next(f for f in flags if f not in shown)
        line = f"{hidden['reason']}. {manager or 'Your care manager'} has been told."
    return {
        "checks": [{"key": k, "label": LABELS[k], "hint": HINTS[k]} for k in CHECKS],
        "visits": visits,
        "streaks": streaks(visits),
        "pct_ok_30d": pct_ok_30d(month),
        "flags": shown,
        # A hidden (not yet acknowledged) amber flag still means "Watching
        # closely" for the family, so the chip matches the sentence.
        "status": status_word(flags, visits),
        "summary_line": line,
        "chips": {k: [{"key": c, "label": l} for c, l in CHIPS[k].items()] for k in CHECKS},
        "baseline": baseline,
        "latest_vitals": next(({"date": v["date"], **v["vitals"]} for v in visits if v["vitals"]), None),
        "explain": (
            "Every visit, your carer checks four things — Safe (home and person), Steady (walking, no falls), "
            "Settled (mood, meals, sleep, medicines) and Connected (in touch, anything to tell you). "
            "Green means as usual. Amber means something changed and your care manager is looking at it. "
            "Red means we call you within 2 hours. This is a care check, not a medical test."
        ),
    }


def acknowledge_flag(db: Session, elder: Elder, key: str, user) -> dict:
    """Care manager has seen a flag; for amber flags the family is told now that someone is on it."""
    view = kushlife_view(db, elder, limit=12, staff=True)
    flag = next((f for f in view["flags"] if f["key"] == key), None)
    if not flag:
        raise_bad_request("That KushLife flag is no longer open")
    db.refresh(elder)
    attrs = dict(elder.custom_attributes or {})
    acks = dict(attrs.get("kushlife_ack") or {})
    who = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
    acks[key] = {"by": who, "at": datetime.now(timezone.utc).isoformat()}
    attrs["kushlife_ack"] = dict(list(acks.items())[-100:])
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    if flag["level"] == "amber":
        from app.livewell.family_notify import notify_family

        notify_family(
            db, elder, "KushLife: keeping an eye on it",
            f"{flag['reason']}. {(user.first_name or 'Your care manager')} has seen it and is following up.",
            event="report",
        )
    return {"key": key, **acks[key]}


def after_visit(db: Session, elder: Elder, job: CareJob, record: dict) -> None:
    """Raise new flags after a visit: manager email for amber/red; red also tells the family.

    Each flag key is sent once (``custom_attributes.kushlife_sent``), so a streak that carries
    on doesn't re-send, and an acknowledged flag stays acknowledged.
    """
    visits = recent_visits(db, elder.id, limit=12)
    if not visits or visits[0]["job_id"] != job.id:
        return  # only the newest visit can raise live flags
    db.refresh(elder)
    attrs = dict(elder.custom_attributes or {})
    sent = list(attrs.get("kushlife_sent") or [])
    flags = [f for f in open_flags(elder, visits) if not f.get("acknowledged_at") and f["key"] not in sent]
    if not flags:
        return
    attrs["kushlife_sent"] = (sent + [f["key"] for f in flags])[-200:]
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()
    from app.livewell.email_notifications import email_staff

    name = f"{elder.first_name} {elder.last_name}".strip()
    top = flags[0]
    lines = "\n".join(f"- {f['reason']}" for f in flags)
    email_staff(
        db, elder, "kushlife_flag",
        f"KushLife {'RED' if top['level'] == 'red' else 'amber'} — {name}",
        f"{lines}\n"
        + ("Call the family within 2 hours and consider a reassessment." if top["level"] == "red"
           else "Look at it within 24 hours and acknowledge it on the client page."),
    )
    if top["level"] == "red":
        from app.livewell.family_notify import notify_family

        notify_family(
            db, elder, "KushLife: we'll call you",
            f"On today's visit we noticed: {top['reason'].lower()}. Your care manager will call you within 2 hours.",
            event="kushlife_red",
        )
