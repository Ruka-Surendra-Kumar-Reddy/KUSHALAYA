"""Live tracking link — no login, the signed link is the key.

``/api/v1/home-safety/track/{token}``: mounted under the Safe Home prefix so nginx
already routes it. One link per trip; it shows the position only while the visit is
on the way, then "Arrived" for a few hours (see ``live_location.public_track``).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.livewell.live_location import public_track

router = APIRouter(prefix="/home-safety/track", tags=["Safe Home — Live tracking"])


@router.get("/{token}")
def track(token: str, db: Session = Depends(get_db)):
    return public_track(db, token[:80])
