from fastapi import APIRouter, Depends, Query

from app.core.geocoding import geocode_address
from app.core.rbac import READ_ROLES, require_roles
from app.core.responses import raise_not_found
from app.models.user import User
from app.schemas.geocode import GeocodeResult

router = APIRouter(prefix="/geocode", tags=["Geocoding"])


@router.get("", response_model=GeocodeResult)
def preview_geocode(
    address: str = Query(..., min_length=3),
    _user: User = Depends(require_roles(*READ_ROLES)),
) -> GeocodeResult:
    coords = geocode_address(address)
    if not coords:
        raise_not_found("Address could not be geocoded")
    lat, lon = coords
    return GeocodeResult(latitude=lat, longitude=lon)
