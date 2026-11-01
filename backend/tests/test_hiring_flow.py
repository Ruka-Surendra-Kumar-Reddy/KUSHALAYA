"""Hiring board: applicant → interview (scorecard note) → training → hired caregiver."""


def test_applicant_to_caregiver(client, seed_tenant):
    res = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"})
    admin = {"Authorization": f"Bearer {res.json()['access_token']}"}
    res = client.post("/api/v1/prospects/caregivers", headers=admin,
                      json={"first_name": "Sita", "last_name": "Rao", "phone": "9876500000", "years_experience": 3})
    assert res.status_code == 200, res.text
    pid = res.json()["id"]
    for stage in ("SCREENING", "INTERVIEW"):
        r = client.patch(f"/api/v1/prospects/caregivers/{pid}/stage", json={"stage": stage}, headers=admin)
        assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/prospects/caregivers/{pid}/activities", headers=admin,
                    json={"activity_type": "NOTE", "body": "Interview scorecard — Communication: 4/5"})
    assert r.status_code == 200, r.text
    for stage in ("DOCS_PENDING", "VERIFICATION", "TRAINING"):
        assert client.patch(f"/api/v1/prospects/caregivers/{pid}/stage", json={"stage": stage},
                            headers=admin).status_code == 200
    hired = client.post(f"/api/v1/prospects/caregivers/{pid}/convert", headers=admin)
    assert hired.status_code == 200, hired.text
    cg_id = hired.json()["caregiver_id"]
    team = client.get("/api/v1/team/caregivers", headers=admin).json()
    assert any(c["id"] == cg_id for c in team)
    notes = client.get(f"/api/v1/prospects/caregivers/{pid}/activities", headers=admin).json()
    assert any("scorecard" in n["body"] for n in notes)
