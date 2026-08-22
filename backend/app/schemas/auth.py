from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    id: int
    display_name: str | None
    email: str | None
    avatar_url: str | None
    role: str
