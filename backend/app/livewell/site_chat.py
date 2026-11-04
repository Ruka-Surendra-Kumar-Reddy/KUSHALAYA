"""Website chat answers ("Hi, I'm Surendra") — step 2: AI replies from our own facts.

Gemini answers a visitor's typed question using only FACTS below plus the plan
list from care_plan_catalog.py (the source of truth for prices; what the page
sends is ignored, so a visitor cannot change a price). Rules:
emergencies always get 112/108 first, prices only from the given list, no medical
advice, and it never claims to be a person — Surendra's team calls back.

Public endpoint, so it is capped per visitor and per day (in memory, per process),
and nothing the visitor types is stored; usage counts go to ai_usage_events.
"""

from __future__ import annotations

import json
import logging
import re
import time

from app.livewell.care_plan_catalog import EVERY_PLAN_INCLUDES, HOME_ASSESSMENT, PLANS, SINGLE_VISIT

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

#: Pages a reply may point to.
LINKS = {
    "/kushcare-discovery": "Book free KushCare Discovery",
    "/packages": "See plans & prices",
    "/safe-homes": "Home safety",
    "/safe-homes#ai": "AI room check",
    "/kushlife": "KushLife visits",
    "/contact": "Contact us",
    "/about": "About us",
    "/blog": "Guides for families",
    "/refund-policy": "Refunds & cancellation",
    "/privacy": "Privacy",
}

EMERGENCY = re.compile(
    r"\b(fall|fell|fallen|emergency|ambulance|unconscious|bleed|bleeding|chest pain|stroke|can'?t breathe|not breathing|heart attack)\b",
    re.I,
)
EMERGENCY_REPLY = (
    "If someone is hurt or unwell right now, please call 112 (or 108 for an ambulance) first. "
    "Then call us on +91 905 905 1085 and we will help."
)

FACTS = """
KushAlaya helps families anywhere in India keep ageing parents safe at home. Many families live in another city or abroad.
- KushCare Discovery: a short online form; we call back within 2 hours. The form, the call and the home assessment visit are all free, with no payment and no obligation. Only a single priority visit has a one-time registration fee (see PLANS). If useful, a home safety assessment visit checks the home room by room and gives a KushAlaya Safety Score out of 100 with a prioritised plan (urgent / can wait) and prices before anything is done.
- Home safety fixes: grab bars, fold-up toilet rails, anti-slip strips and coatings, bed rails, motion night lights, handrails, shower chairs; fitted by our partners and checked when done. Product prices are quoted before booking.
- AI room check: families can send a room photo; AI points out common risks (no grab bar, slippery floor, loose rug); a care manager reviews every finding. AI room preview shows the room with products fitted; it is an illustration, the final products are confirmed at the visit. Photos are used only for the home's plan and never shared or sold.
- KushLife visits: caregivers visit regularly and record four checks every visit (safe, steady, settled, connected) with a note; families see updates after every visit, a weekly summary and a monthly letter in the family app (family.kushalaya.com). Caregivers are BLS/CPR trained and give non-medical support.
- Also available: physiotherapy at home, medicine reminders, help coordinating hospital visits. A complimentary SOS watch with family alerts comes with the Privilege and Signature plans.
- Every plan has care-manager visits (see PLANS for how many). Do not promise a "named" or "dedicated" care manager.
- KushAlaya is not an emergency service: in an emergency call 112 or 108 first.
- Contact: India +91 905 905 1085, US & Canada +1 (678) 481-8252, WhatsApp, contact@kushalaya.com. Team: Krish Posa (Founder), Bharani (CTO & Head of Care), Surendra (Software Developer).
- Payments in rupees with GST invoices; cancelling a paid order before it starts returns the full amount to the family wallet.
""".strip()

RULES = """
You are KushAlaya's website assistant, answering in the chat for Surendra's team.
- Answer ONLY using the facts and plan list given. If the answer is not there, say you're not sure and offer a call back.
- Never invent prices, discounts, timings, locations, staff or guarantees. Quote prices only from the plan list.
- No medical diagnosis or advice; suggest speaking to a doctor. Emergencies: 112/108 first.
- If asked whether you are a person: say you are KushAlaya's assistant and Surendra's team will call them back.
- Do not ask for health details in chat. You may suggest leaving a name and phone for a call back.
- Never say you have noted, saved or passed on anyone's details: you cannot. Ask them to type their name and phone number here, or use the call-back form.
- Reply in the visitor's language if it is Hindi, Telugu, Tamil, Kannada or English. Warm, plain, 1-4 short sentences.
Reply with JSON only: {"reply": "<text>", "link": "<one of the allowed paths or null>", "offer_callback": true|false}
""".strip()

PER_IP_LIMIT = 20  # messages per visitor per 10 minutes
PER_IP_WINDOW = 600.0
DAILY_LIMIT = 1500  # messages per day across all visitors (per process)

_hits: dict[str, list[float]] = {}
_day = {"date": "", "count": 0}


def allow(ip: str) -> bool:
    """Per-visitor and daily caps; True when this message may go to the AI."""
    now = time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    if _day["date"] != today:
        _day.update(date=today, count=0)
    if _day["count"] >= DAILY_LIMIT:
        return False
    cutoff = now - PER_IP_WINDOW
    hits = [t for t in _hits.get(ip, []) if t > cutoff]
    if len(hits) >= PER_IP_LIMIT:
        _hits[ip] = hits
        return False
    hits.append(now)
    _hits[ip] = hits
    _day["count"] += 1
    if len(_hits) > 5000:  # keep memory bounded
        for k in [k for k, v in _hits.items() if not v or v[-1] <= cutoff]:
            _hits.pop(k, None)
    return True


def _inr(paise: int) -> str:
    """₹1,25,000 — whole rupees, Indian grouping."""
    rupees = str(int(paise) // 100)
    if len(rupees) > 3:
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", rupees[:-3])
        return f"₹{head},{rupees[-3:]}"
    return f"₹{rupees}"


def _plan_lines(plans: list[dict] | None = None) -> str:
    """Plan facts from the catalog. `plans` (what the page sent) is ignored."""
    out = [f"- Every annual plan includes: {'; '.join(EVERY_PLAN_INCLUDES)}."]
    for p in PLANS:
        tag = " Most popular." if p.get("popular") else ""
        out.append(
            f"- {p['name']}: {_inr(p['annual_paise'])} a year, or {_inr(p['monthly_paise'])} a month if paid monthly "
            f"(costs more than yearly). {p['visits_per_year']} care-manager visits a year. "
            f"{p['summary']}.{tag} Plus: {'; '.join(p['inclusions'])}."
        )
    out.append("- Monthly billing is available on every plan.")
    out.append(
        f"- {SINGLE_VISIT['name']}: {_inr(SINGLE_VISIT['price_paise'])} + {_inr(SINGLE_VISIT['registration_paise'])} "
        f"registration, {SINGLE_VISIT['hours']} hours, no subscription."
    )
    fee = HOME_ASSESSMENT["price_paise"]
    out.append(f"- {HOME_ASSESSMENT['name']}: {_inr(fee) if fee else 'Free'}.")
    out.append("- All prices include GST.")
    return "\n".join(out)


def _call_gemini(prompt: str) -> dict | None:
    """Raw call; returns parsed JSON or None. Patched in tests."""
    import httpx

    from app.core.config import settings

    key = (settings.GEMINI_API_KEY or "").strip()
    if not key:
        return None
    models = [settings.AI_VISION_MODEL] + [m.strip() for m in (settings.AI_VISION_MODEL_FALLBACKS or "").split(",") if m.strip()]
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # Thinking models spend output tokens before the answer: leave plenty of room.
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "maxOutputTokens": 4096},
    }
    for model in dict.fromkeys(m for m in models if m):
        try:
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(GEMINI_URL.format(model=model), params={"key": key}, json=body)
        except Exception as exc:
            log.warning("site chat request failed: %s", type(exc).__name__)
            return None
        if resp.status_code == 404:
            continue
        if resp.status_code >= 400:
            log.warning("site chat HTTP %s", resp.status_code)
            return None
        try:
            parts = resp.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought"))
            data = json.loads(text)
            if isinstance(data, dict):
                data["_model"] = model
                return data
            log.warning("site chat: unexpected reply shape from %s", model)
        except Exception as exc:
            log.warning("site chat: could not read reply from %s (%s)", model, type(exc).__name__)
            return None
    return None


def answer(question: str, history: list[dict], plans: list[dict]) -> dict:
    """{"reply", "link", "link_label", "offer_callback", "source": ai|emergency|fallback, "model"}"""
    q = " ".join(str(question or "").split())[:500]
    if EMERGENCY.search(q):
        return {"reply": EMERGENCY_REPLY, "link": None, "link_label": None, "offer_callback": False, "source": "emergency"}
    turns = []
    for h in (history or [])[-6:]:
        if isinstance(h, dict) and h.get("text"):
            who = "Visitor" if h.get("from") == "me" else "Assistant"
            turns.append(f"{who}: {' '.join(str(h['text']).split())[:400]}")
    prompt = (
        f"{RULES}\n\nAllowed link paths: {', '.join(LINKS)}\n\nFACTS:\n{FACTS}\n\nPLANS (current prices):\n{_plan_lines(plans)}\n\n"
        + ("Conversation so far:\n" + "\n".join(turns) + "\n\n" if turns else "")
        + f"Visitor: {q}"
    )
    data = _call_gemini(prompt)
    reply = str((data or {}).get("reply") or "").strip()
    if not reply:
        return {
            "reply": "Thanks — the quickest way to a proper answer is a short call. Leave your number and we'll call you back.",
            "link": None,
            "link_label": None,
            "offer_callback": True,
            "source": "fallback",
        }
    link = (data or {}).get("link")
    link = link if link in LINKS else None
    return {
        "reply": reply[:900],
        "link": link,
        "link_label": LINKS.get(link) if link else None,
        "offer_callback": bool((data or {}).get("offer_callback")),
        "source": "ai",
        "model": (data or {}).get("_model"),
    }


# --- Call-back requests typed into the chat -------------------------------------------
# "I'm Ravi, 98765 43210, please call" must become a lead, not an AI promise.
_PHONE_RE = re.compile(r"(?<![\d+])(\+?\d[\d\s().-]{8,18}\d)(?!\d)")
_NAME_RE = re.compile(
    r"\b(?:my name is|i am|i'm|im|this is|name\s*[:-])\s+([A-Za-z][A-Za-z.]{1,30}(?:\s+[A-Za-z][A-Za-z.]{1,30}){0,2})",
    re.IGNORECASE,
)
_NAME_STOP = {"and", "i", "my", "with", "live", "lives", "looking", "interested", "calling", "from", "in", "the", "a", "an", "not", "very", "worried", "here", "abroad", "living"}


def find_phone(text: str) -> str | None:
    """A phone number in free text (Indian mobile or international), digits 10-15."""
    for m in _PHONE_RE.finditer(text or ""):
        raw = m.group(1)
        digits = re.sub(r"\D", "", raw)
        if 10 <= len(digits) <= 15:
            return ("+" if raw.strip().startswith("+") else "") + digits
    return None


def find_name(texts: list[str]) -> str:
    for t in reversed(texts):
        m = _NAME_RE.search(t or "")
        if m:
            words = []
            for w in m.group(1).split():
                if w.lower().strip(".") in _NAME_STOP:
                    break
                words.append(w.strip("."))
            if words:
                return " ".join(words)[:60].title()
    return ""


def capture_lead(db, message: str, history: list[dict], *, source_ip: str | None) -> dict | None:
    """When the visitor's message has a phone number, add a Leads-board enquiry (once per
    number per day) and return the confirmation to show; None when there is no number or
    it isn't a valid one (the AI answers as usual then)."""
    phone = find_phone(message)
    if not phone:
        return None
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException

    from app.livewell.public_enquiry_service import PublicEnquiryService
    from app.models.elder_prospect import ElderProspect

    mine = [h.get("text", "") for h in history if h.get("from") == "me"] + [message]
    name = find_name(mine)
    digits = re.sub(r"\D", "", phone)[-10:]
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    recent = (
        db.query(ElderProspect)
        .filter(ElderProspect.created_at >= since, ElderProspect.phone.isnot(None))
        .order_by(ElderProspect.id.desc())
        .limit(200)
        .all()
    )
    dup = next((r for r in recent if re.sub(r"\D", "", r.phone or "")[-10:] == digits), None)
    if dup is None:
        transcript = "\n".join(
            f"{'Visitor' if h.get('from') == 'me' else 'Chat'}: {str(h.get('text', ''))[:300]}" for h in history[-6:]
        )
        notes = "Typed into the website chat:\n" + (transcript + "\n" if transcript else "") + f"Visitor: {message[:500]}"
        try:
            dup = PublicEnquiryService.create(
                db,
                name=name or "Website chat visitor",
                phone=phone,
                email=None,
                area=None,
                services=None,
                visit_frequency=None,
                products=None,
                notes=notes,
                kind="website-chat",
                source_ip=source_ip if source_ip and source_ip != "unknown" else None,
            )
        except HTTPException:
            return None  # not a valid phone, or too many enquiries: answer normally
    who = f", {name.split()[0]}" if name else ""
    return {
        "reference": f"KA-{dup.id:06d}",
        "reply": (
            f"Thank you{who}. Your call-back request is with our team (reference KA-{dup.id:06d}). "
            "We'll call you within 2 hours (8 am to 8 pm IST). If it's urgent, call or WhatsApp us."
        ),
    }

