"""Blog: admin-only CRUD, public visibility, slugs, scheduling, Markdown cleaning, the seed post."""

from datetime import datetime, timedelta, timezone

from app.livewell.blog import clean_markdown, reading_minutes, slugify
from app.livewell.blog_seed import SAMPLE_SLUG, seed_marketing_posts, seed_sample_post
from app.models.blog import BlogPost

A = "/api/v1/blog"
P = "/api/v1/public/blog"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _post(client, headers, **body):
    body = {"title": "Staying safe at home", "body_md": "## Hello\n\nSome words here.", **body}
    res = client.post(f"{A}/posts", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


def test_admin_crud(client, seed_tenant, admin_headers):
    p = _post(client, admin_headers, excerpt="Short summary", tags=["Home Safety", "home safety", " Hyderabad "])
    assert p["slug"] == "staying-safe-at-home" and p["status"] == "draft"
    assert p["tags"] == ["home safety", "hyderabad"] and p["reading_minutes"] == 1
    assert p["author_name"] == "Test Admin"
    upd = client.put(f"{A}/posts/{p['id']}", json={"title": "New title", "slug": "My Custom Slug"}, headers=admin_headers)
    assert upd.status_code == 200 and upd.json()["slug"] == "my-custom-slug" and upd.json()["title"] == "New title"
    assert any(x["id"] == p["id"] for x in client.get(f"{A}/posts", headers=admin_headers).json())
    assert client.get(f"{A}/posts/{p['id']}", headers=admin_headers).json()["title"] == "New title"
    assert client.delete(f"{A}/posts/{p['id']}", headers=admin_headers).status_code == 204
    assert client.get(f"{A}/posts/{p['id']}", headers=admin_headers).status_code == 404


def test_manager_and_viewer_are_refused(client, seed_tenant, admin_headers):
    p = _post(client, admin_headers)
    for email in ("manager@test.example", "viewer@test.example"):
        h = _login(client, email)
        assert client.get(f"{A}/posts", headers=h).status_code == 403
        assert client.post(f"{A}/posts", json={"title": "X"}, headers=h).status_code == 403
        assert client.put(f"{A}/posts/{p['id']}", json={"title": "X"}, headers=h).status_code == 403
        assert client.delete(f"{A}/posts/{p['id']}", headers=h).status_code == 403
    assert client.get(f"{A}/posts").status_code in (401, 403)


def test_validation(client, seed_tenant, admin_headers):
    assert client.post(f"{A}/posts", json={"title": "  "}, headers=admin_headers).status_code == 400
    assert client.post(f"{A}/posts", json={"title": "T", "excerpt": "x" * 161}, headers=admin_headers).status_code == 400
    assert client.post(f"{A}/posts", json={"title": "T", "canonical_url": "javascript:alert(1)"}, headers=admin_headers).status_code == 400
    p = _post(client, admin_headers, body_md="![](/x.png)")
    # Images need alt text before the post can go live; so does the cover.
    assert client.put(f"{A}/posts/{p['id']}", json={"status": "published"}, headers=admin_headers).status_code == 400
    q = _post(client, admin_headers, cover_image_url="/marketing/blog/cover.webp")
    assert client.put(f"{A}/posts/{q['id']}", json={"status": "published"}, headers=admin_headers).status_code == 400
    ok = client.put(f"{A}/posts/{q['id']}", json={"status": "published", "cover_image_alt": "A cover"}, headers=admin_headers)
    assert ok.status_code == 200 and ok.json()["published_at"]
    # Scheduling needs a time.
    assert client.put(f"{A}/posts/{p['id']}", json={"status": "scheduled"}, headers=admin_headers).status_code == 400


def test_slug_unique(client, seed_tenant, admin_headers):
    a = _post(client, admin_headers)
    b = _post(client, admin_headers)
    assert a["slug"] == "staying-safe-at-home" and b["slug"] == "staying-safe-at-home-2"
    clash = client.put(f"{A}/posts/{b['id']}", json={"slug": a["slug"]}, headers=admin_headers)
    assert clash.status_code == 409
    assert client.post(f"{A}/posts", json={"title": "Other", "slug": a["slug"]}, headers=admin_headers).status_code == 409


def test_public_sees_only_published(client, seed_tenant, admin_headers):
    draft = _post(client, admin_headers, title="Draft post")
    live = _post(client, admin_headers, title="Live post", tags=["falls"])
    client.put(f"{A}/posts/{live['id']}", json={"status": "published"}, headers=admin_headers)
    slugs = [x["slug"] for x in client.get(f"{P}/posts").json()["items"]]
    assert "live-post" in slugs and "draft-post" not in slugs
    assert client.get(f"{P}/posts/draft-post").status_code == 404
    one = client.get(f"{P}/posts/live-post").json()
    assert one["title"] == "Live post" and "status" not in one and "related" in one
    assert client.get(f"{P}/posts", params={"tag": "falls"}).json()["total"] == 1
    assert client.get(f"{P}/posts", params={"tag": "nothing"}).json()["total"] == 0
    assert "live-post" in [x["slug"] for x in client.get(f"{P}/sitemap").json()]
    # Unpublish hides it again.
    client.put(f"{A}/posts/{live['id']}", json={"status": "draft"}, headers=admin_headers)
    assert client.get(f"{P}/posts/live-post").status_code == 404
    assert draft["status"] == "draft"


def test_pagination(client, seed_tenant, admin_headers):
    for i in range(4):
        p = _post(client, admin_headers, title=f"Post {i}")
        client.put(f"{A}/posts/{p['id']}", json={"status": "published"}, headers=admin_headers)
    page2 = client.get(f"{P}/posts", params={"per_page": 3, "page": 2}).json()
    assert page2["pages"] >= 2 and len(page2["items"]) >= 1


def test_scheduled_visibility(client, seed_tenant, admin_headers):
    p = _post(client, admin_headers, title="Later post")
    res = client.put(
        f"{A}/posts/{p['id']}", json={"status": "scheduled", "publish_at": _iso(timedelta(days=1))}, headers=admin_headers
    )
    assert res.status_code == 200 and res.json()["status"] == "scheduled" and not res.json()["live"]
    assert client.get(f"{P}/posts/later-post").status_code == 404
    client.put(f"{A}/posts/{p['id']}", json={"publish_at": _iso(timedelta(minutes=-5))}, headers=admin_headers)
    seen = client.get(f"{P}/posts/later-post")
    assert seen.status_code == 200 and seen.json()["published_at"]


def test_markdown_sanitised(client, seed_tenant, admin_headers):
    nasty = (
        "Hi <script>alert(1)</script> there <img src=x onerror=alert(2)>\n\n"
        "[click](javascript:alert(3)) [ok](https://example.com) <https://kushalaya.com>\n\n"
        "[ref]: data:text/html;base64,xx\n<scr<script>ipt>bad()</script>"
    )
    p = _post(client, admin_headers, body_md=nasty)
    body = p["body_md"]
    assert "onerror" not in body.lower()
    assert "<script" not in body.lower() and "<img" not in body.lower()
    assert "javascript:" not in body.lower() and "data:" not in body.lower()
    assert "[ok](https://example.com)" in body and "https://kushalaya.com" in body
    assert "[click](#)" in body


def test_image_upload_admin_only(client, seed_tenant, admin_headers, auth_headers):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    files = {"file": ("a.png", png, "image/png")}
    assert client.post(f"{A}/images", files=files, data={"alt": "x"}, headers=auth_headers).status_code == 403
    res = client.post(f"{A}/images", files=files, data={"alt": "A grab bar"}, headers=admin_headers)
    assert res.status_code == 201, res.text
    url = res.json()["url"]
    assert url.startswith("/api/v1/public/blog/images/")
    got = client.get(url)
    assert got.status_code == 200 and got.content == png
    bad = client.post(f"{A}/images", files={"file": ("a.txt", b"hi", "text/plain")}, headers=admin_headers)
    assert bad.status_code == 400


def test_seed_idempotent(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    assert seed_sample_post(db, tid) is True
    assert seed_sample_post(db, tid) is False
    rows = db.query(BlogPost).filter(BlogPost.tenant_id == tid, BlogPost.slug == SAMPLE_SLUG).all()
    assert len(rows) == 1
    post = rows[0]
    assert post.status == "published" and len(post.excerpt) <= 160 and post.faq
    for link in ("/kushcare-discovery", "/kushlife", "/packages"):
        assert f"]({link})" in post.body_md
    assert "<" not in post.body_md
    assert 900 <= len(post.body_md.split()) <= 1300


def test_helpers():
    assert slugify("Caring for Parents — Hyderabad!") == "caring-for-parents-hyderabad"
    assert slugify("  ") == "post"
    assert reading_minutes("word " * 401) == 3
    assert reading_minutes("") == 1
    assert clean_markdown("a <b>bold</b> move") == "a bold move"


def test_marketing_posts_publish_once(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    assert seed_marketing_posts(db, tid) == 4
    assert seed_marketing_posts(db, tid) == 0
    rows = db.query(BlogPost).filter(BlogPost.tenant_id == tid).all()
    assert len(rows) == 4 and all(p.status == "published" and p.published_at for p in rows)
    assert all(len(p.excerpt) <= 160 and len(p.seo_title) <= 70 and p.cover_image_alt for p in rows)
    assert not any(bad in p.body_md for p in rows for bad in ("/how-it-works", "/care-plans", "(/elder-care)"))
