from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str


class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True