"""Blog: admin CRUD (ops → Blog, admins only) and the public read API for www /blog."""

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, require_roles
from app.livewell import blog
from app.models.user import User

router = APIRouter(prefix="/blog", tags=["Blog (admin)"])
public_router = APIRouter(prefix="/public/blog", tags=["Blog (public)"])


@router.get("/posts")
def list_posts(db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    return blog.list_admin(db, user)


@router.post("/posts", status_code=201)
def create_post(body: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    return blog.create_post(db, user, body)


@router.get("/posts/{post_id}")
def get_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    return blog.get_admin(db, user, post_id)


@router.put("/posts/{post_id}")
def update_post(
    post_id: int, body: dict, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))
):
    return blog.update_post(db, user, post_id, body)


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    blog.delete_post(db, user, post_id)
    return Response(status_code=204)


@router.post("/images", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    alt: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    content = await file.read()
    return blog.save_image(db, user, content, file.content_type or "", file.filename or "image", alt)


# --- Public (no sign-in): published posts of the site tenant only -------------------


@public_router.get("/posts")
def public_posts(
    page: int = Query(1, ge=1, le=1000),
    per_page: int = Query(9, ge=1, le=50),
    tag: str | None = Query(None, max_length=40),
    db: Session = Depends(get_db),
):
    return blog.public_list(db, page=page, per_page=per_page, tag=tag)


@public_router.get("/sitemap")
def public_sitemap(db: Session = Depends(get_db)):
    return blog.public_sitemap(db)


@public_router.get("/posts/{slug}")
def public_post(slug: str, db: Session = Depends(get_db)):
    return blog.public_post(db, slug)


@public_router.get("/images/{image_id}")
def public_image(image_id: int, db: Session = Depends(get_db)):
    content, mime = blog.image_bytes(db, image_id)
    return Response(content=content, media_type=mime, headers={"Cache-Control": "public, max-age=31536000, immutable"})
