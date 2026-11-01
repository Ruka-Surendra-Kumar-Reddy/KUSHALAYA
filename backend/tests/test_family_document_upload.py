"""Family document upload — what families may share with the care team.

These files are served back from our own origin, so the allowlist and the
filename handling are security controls, not cosmetics.
"""

import pytest
from workforceos_core.exceptions import WorkforceHTTPError

from app.livewell.family_care_hub import FamilyCareHubService, _safe_file_name
from app.livewell.document_types import (
    FAMILY_UPLOAD_TYPE_CODES,
    LW_FAMILY_MEDICAL,
    LW_FAMILY_OTHER,
)
from app.models.document import Document
from app.models.elder import Elder as ElderModel
from app.models.user import User as UserModel
from app.core.security import hash_password

PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n"


@pytest.fixture
def elder(db, seed_tenant):
    row = ElderModel(
        first_name="Lakshmi",
        last_name="Reddy",
        tenant_id=seed_tenant["tenant"].id,
    )
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def family_user(db, seed_tenant, elder):
    user = UserModel(
        email="family.upload@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Arjun",
        last_name="Reddy",
        role="ELDER_PORTAL",
        tenant_id=seed_tenant["tenant"].id,
        elder_id=elder.id,
        portal_relationship="family",
    )
    db.add(user)
    db.flush()
    return user


def upload(db, user, **kw):
    params = {
        "file_name": "report.pdf",
        "content": PDF,
        "content_type": "application/pdf",
        "document_type": LW_FAMILY_MEDICAL,
    }
    params.update(kw)
    return FamilyCareHubService.upload_document(db, user, **params)


def test_family_can_upload_a_pdf(db, family_user, elder):
    result = upload(db, family_user, note="Cardiology report")
    assert result["uploaded_by_family"] is True
    assert result["document_type"] == LW_FAMILY_MEDICAL

    doc = db.query(Document).filter(Document.id == result["id"]).first()
    assert doc is not None
    # Stored against the elder, which is what makes it visible in the ops
    # documents view for that client.
    assert doc.entity_type == "elder"
    assert doc.entity_id == elder.id
    assert doc.tenant_id == elder.tenant_id
    assert doc.uploaded_by_user_id == family_user.id
    assert doc.file_size_bytes == len(PDF)


def test_upload_appears_in_the_family_document_list(db, family_user):
    upload(db, family_user, note="Blood test")
    rows = FamilyCareHubService.list_documents(db, family_user)
    assert any(r["uploaded_by_family"] and r["title"] == "Blood test" for r in rows)


def test_family_can_read_back_their_own_upload(db, family_user):
    result = upload(db, family_user)
    content, mime, name = FamilyCareHubService.read_document_file(
        db, family_user, result["id"]
    )
    assert content == PDF
    assert mime == "application/pdf"
    assert name.endswith(".pdf")


class TestRejections:
    def test_script_bearing_types_are_refused(self, db, family_user):
        # The stored-XSS cases: these would execute in our origin if served.
        for mime, name in [
            ("text/html", "evil.html"),
            ("image/svg+xml", "evil.svg"),
            ("application/x-msdownload", "evil.exe"),
            ("text/javascript", "evil.js"),
        ]:
            with pytest.raises(WorkforceHTTPError):
                upload(db, family_user, content_type=mime, file_name=name)

    def test_oversized_file_is_refused(self, db, family_user):
        from app.core.config import settings

        too_big = b"%PDF-1.4" + b"0" * (int(settings.MAX_UPLOAD_MB) * 1024 * 1024 + 1)
        with pytest.raises(WorkforceHTTPError):
            upload(db, family_user, content=too_big)

    def test_empty_file_is_refused(self, db, family_user):
        with pytest.raises(WorkforceHTTPError):
            upload(db, family_user, content=b"")

    def test_unknown_document_type_is_refused(self, db, family_user):
        with pytest.raises(WorkforceHTTPError):
            upload(db, family_user, document_type="LW_NOT_A_TYPE")

    def test_signed_form_types_cannot_be_forged_by_family(self, db, family_user):
        # A family must not be able to file something as a signed agreement.
        with pytest.raises(WorkforceHTTPError):
            upload(db, family_user, document_type="LW_SERVICE_AGREEMENT")


class TestSafeFileName:
    def test_extension_follows_the_validated_mime(self):
        # Uploader-supplied extension is never trusted.
        assert _safe_file_name("evil.html", "application/pdf") == "evil.pdf"
        assert _safe_file_name("scan.jpeg", "image/png") == "scan.png"

    def test_path_traversal_is_stripped(self):
        assert _safe_file_name("../../etc/passwd", "application/pdf") == "passwd.pdf"
        assert _safe_file_name(r"C:\Windows\system32\x.pdf", "application/pdf") == "x.pdf"

    def test_odd_characters_are_normalised(self):
        out = _safe_file_name("my report (final);rm -rf.pdf", "application/pdf")
        assert out.endswith(".pdf")
        assert " " not in out and ";" not in out

    def test_blank_name_still_produces_a_file(self):
        assert _safe_file_name("", "application/pdf") == "document.pdf"


def test_all_family_types_are_accepted(db, family_user):
    for code in FAMILY_UPLOAD_TYPE_CODES:
        result = upload(db, family_user, document_type=code, file_name=f"{code}.pdf")
        assert result["document_type"] == code


def test_other_type_defaults_its_title(db, family_user):
    result = upload(db, family_user, document_type=LW_FAMILY_OTHER, note=None)
    assert result["title"]
