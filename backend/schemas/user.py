from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    business_name: str
    email: EmailStr
    password: str
    contact: str | None = None
    address: str | None = None
    role: str = "business"


class UserOut(BaseModel):
    id: int
    business_name: str
    email: EmailStr
    contact: str | None = None
    address: str | None = None
    role: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
