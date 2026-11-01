"""Website chat answers (Surendra chat step 2): emergency first, safe links, fallback, caps."""

from app.livewell import site_chat

PLANS = [{"name": "Essential", "annual_inr": 12000, "monthly_inr": 1200, "summary": "1 visit a month."}]


def test_emergency_never_goes_to_ai(monkeypatch):
    called = []
    monkeypatch.setattr(site_chat, "_call_gemini", lambda p: called.append(p) or {"reply": "x"})
    out = site_chat.answer("My mother had a fall and is bleeding", [], PLANS)
    assert out["source"] == "emergency" and "112" in out["reply"] and not called


def test_ai_reply_uses_plans_and_only_allowed_links(monkeypatch):
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return {"reply": "Essential is ₹12,000 a year.", "link": "https://evil.example", "offer_callback": False}

    monkeypatch.setattr(site_chat, "_call_gemini", fake)
    out = site_chat.answer("How much is the basic plan?", [{"from": "bot", "text": "Hi"}], PLANS)
    assert out["source"] == "ai" and out["reply"].startswith("Essential")
    assert out["link"] is None  # not in the allowed list
    assert "Never invent prices" in seen["prompt"]
    # Prices come from the catalog, not from what the page sent.
    assert "₹12,000" not in seen["prompt"]
    assert "KushAlaya Privilege: ₹1,25,000 a year, or ₹13,500 a month if paid monthly" in seen["prompt"]
    assert "KushAlaya Assurance: ₹55,000 a year, or ₹6,000 a month if paid monthly" in seen["prompt"]
    assert "yearly only" not in seen["prompt"]
    assert "Every annual plan includes: Care-manager visits" in seen["prompt"]
    assert "Single priority visit: ₹3,400 + ₹100 registration, 4 hours" in seen["prompt"]
    assert "KushCare Discovery home assessment: Free" in seen["prompt"]
    assert "Never say it is free" not in seen["prompt"]
    assert "effective" not in seen["prompt"]

    monkeypatch.setattr(site_chat, "_call_gemini", lambda p: {"reply": "See plans.", "link": "/packages"})
    assert site_chat.answer("plans?", [], PLANS)["link_label"] == "See plans & prices"


def test_fallback_offers_call_back(monkeypatch):
    monkeypatch.setattr(site_chat, "_call_gemini", lambda p: None)
    out = site_chat.answer("Do you do night care?", [], [])
    assert out["source"] == "fallback" and out["offer_callback"] is True


def test_per_visitor_cap(monkeypatch):
    monkeypatch.setattr(site_chat, "_hits", {})
    monkeypatch.setattr(site_chat, "_day", {"date": "", "count": 0})
    assert all(site_chat.allow("1.2.3.4") for _ in range(site_chat.PER_IP_LIMIT))
    assert site_chat.allow("1.2.3.4") is False
    assert site_chat.allow("5.6.7.8") is True


def test_endpoint(client, monkeypatch):
    monkeypatch.setattr(site_chat, "_hits", {})
    monkeypatch.setattr(site_chat, "_call_gemini", lambda p: {"reply": "Hello!", "link": "/kushcare-discovery", "offer_callback": True, "_model": "m"})
    r = client.post("/api/v1/public/chat", json={"message": "hi", "history": [{"from": "me", "text": "x"}], "plans": PLANS})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "Hello!" and body["link"] == "/kushcare-discovery" and "model" not in body
    assert client.post("/api/v1/public/chat", json={"message": ""}).status_code == 422


def test_phone_typed_in_chat_becomes_a_lead_once(client, db, seed_tenant, monkeypatch):
    """Owner report 2026-10-29: details typed into the chat never reached Leads."""
    from app.models.elder_prospect import ElderProspect

    monkeypatch.setattr(site_chat, "_hits", {})
    called = []
    monkeypatch.setattr(site_chat, "_call_gemini", lambda p: called.append(p) or {"reply": "x"})
    body = {"message": "Hi I am Ravi Kumar, my number is 98765 43210, please call me", "history": []}
    res = client.post("/api/v1/public/chat", json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["source"] == "lead" and out["reference"].startswith("KA-") and "Ravi" in out["reply"]
    assert not called  # no AI promise; the lead is real
    row = db.query(ElderProspect).filter(ElderProspect.phone.isnot(None)).order_by(ElderProspect.id.desc()).first()
    assert row.first_name == "Ravi" and row.stage == "NEW" and "website-chat" in row.source
    assert "98765 43210" in row.notes
    # Same number again the same day: same reference, no second lead.
    again = client.post("/api/v1/public/chat", json=body).json()
    assert again["reference"] == out["reference"]
    assert db.query(ElderProspect).filter(ElderProspect.source.like("%website-chat%")).count() == 1


def test_question_without_phone_goes_to_ai(client, monkeypatch):
    monkeypatch.setattr(site_chat, "_hits", {})
    monkeypatch.setattr(site_chat, "_call_gemini", lambda p: {"reply": "Plans start at 55,000.", "link": "/packages"})
    out = client.post("/api/v1/public/chat", json={"message": "What do plans cost for 2 visits?", "history": []}).json()
    assert out["source"] == "ai" and "reference" not in out


def test_find_phone_and_name():
    assert site_chat.find_phone("call +1 (678) 481-8252") == "+16784818252"
    assert site_chat.find_phone("pin 500039, 2 parents") is None
    assert site_chat.find_name(["my name is sita devi and I live abroad"]) == "Sita Devi"
