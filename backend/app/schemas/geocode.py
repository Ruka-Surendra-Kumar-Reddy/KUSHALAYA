from pydantic import BaseModel


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
