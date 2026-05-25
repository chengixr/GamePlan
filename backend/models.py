from pydantic import BaseModel, Field

class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)

class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateProfileRequest(BaseModel):
    nickname: str | None = None
    avatar: str | None = None

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)

class UserResponse(BaseModel):
    id: int
    username: str
    nickname: str = ""
    avatar: str = "1"

class GameResponse(BaseModel):
    id: int
    steam_app_id: int
    name: str
    name_cn: str = ""
    description: str
    image_url: str
    price: str
    tags: list[str] = []

class RatingRequest(BaseModel):
    game_id: int
    score: int = Field(ge=1, le=5)

class RatingResponse(BaseModel):
    game_id: int
    score: int

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
