"""Client document vault: staff upload; the family sees shared files, not staff-only ones."""


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_vault_upload_visibility(client, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    admin = _login(client, "admin@test.example")
    res = client.post(f"/api/v1/team/clients/{elder.id}/family-logins",
                      json={"email": "vault.son@family.example", "password": "familypass1"}, headers=admin)
    assert res.status_code == 201, res.text

    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    for kind, name in (("LW_FAMILY_MEDICAL", "report.pdf"), ("LW_STAFF_ONLY", "internal.pdf")):
        res = client.post(
            "/api/v1/documents/upload",
            data={"entity_type": "elder", "entity_id": str(elder.id), "document_type": kind},
            files={"file": (name, pdf, "application/pdf")},
            headers=auth_headers,
        )
        assert res.status_code == 200, res.text

    prof = client.get(f"/api/v1/home-safety/clients/{elder.id}/profile", headers=auth_headers).json()
    assert {d["document_type"] for d in prof["documents"]} >= {"LW_FAMILY_MEDICAL", "LW_STAFF_ONLY"}

    fam = _login(client, "vault.son@family.example", "familypass1")
    docs = client.get("/api/v1/home-safety/family/documents", headers=fam).json()
    kinds = {d["document_type"]: d for d in docs}
    assert "LW_FAMILY_MEDICAL" in kinds and "LW_STAFF_ONLY" not in kinds
    assert kinds["LW_FAMILY_MEDICAL"]["uploaded_by_family"] is False
