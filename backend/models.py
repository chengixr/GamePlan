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
    is_admin: bool = False

class GameResponse(BaseModel):
    id: int
    steam_app_id: int
    name: str
    name_cn: str = ""
    description: str
    image_url: str
    image_large: str = ""
    fallback_image: str = ""
    price: str
    tags: list[str] = []
    screenshots: list = []

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

class AdminUserResponse(BaseModel):
    id: int
    username: str
    nickname: str
    avatar: str = "1"
    is_active: bool = True
    is_admin: bool = False
    rating_count: int = 0
    created_at: str = ""

class AdminSyncStatusResponse(BaseModel):
    running: bool
    last_complete: str = ""
    next_scheduled: str = ""

class AdminLogResponse(BaseModel):
    lines: list[str]
    total: int

class AdminSchedulerJobResponse(BaseModel):
    id: str
    name: str
    description: str
    cron: str
    next_run: str = ""
    last_run: str = ""
    last_status: str = "pending"
    last_error: str = ""
