"""Product photos: marketing picture by default; admins upload / remove their own."""

import io


def _admin(client):
    res = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_product_photo_upload_and_reset(client, seed_tenant, auth_headers):
    admin = _admin(client)
    products = client.get("/api/v1/products", headers=admin).json()
    bar = next(p for p in products if p["name"] == "Fixed grab bar")
    assert bar["image_url"] == "/marketing/products/catalog/bth-001.webp" and not bar["has_own_image"]

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    bad = client.post(f"/api/v1/products/{bar['id']}/image", files={"file": ("a.gif", io.BytesIO(png), "image/gif")},
                      headers=admin)
    assert bad.status_code == 400
    assert client.post(f"/api/v1/products/{bar['id']}/image", files={"file": ("a.png", io.BytesIO(png), "image/png")},
                       headers=auth_headers).status_code == 403  # managers can't
    res = client.post(f"/api/v1/products/{bar['id']}/image", files={"file": ("a.png", io.BytesIO(png), "image/png")},
                      headers=admin)
    assert res.status_code == 200, res.text
    url = res.json()["image_url"]
    assert url.startswith(f"/api/v1/product-images/{bar['id']}?v=")
    img = client.get(url)  # no token needed
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"

    reset = client.delete(f"/api/v1/products/{bar['id']}/image", headers=admin).json()
    assert reset["image_url"] == "/marketing/products/catalog/bth-001.webp"
