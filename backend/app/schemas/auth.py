"""认证与用户管理 Pydantic DTO。"""

from datetime import datetime

from pydantic import BaseModel, Field


# ── Login ──

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserInfoResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role_name: str
    is_superadmin: bool
    password_is_default: bool
    permissions: list[str]

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfoResponse


# ── User CRUD ──

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(default="", max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    role_id: int


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=50)
    role_id: int | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role_id: int
    role_name: str
    is_active: bool
    is_superadmin: bool
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserStatusPatch(BaseModel):
    is_active: bool


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


class ChangeOwnPassword(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


# ── Role CRUD ──

class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = Field(default="", max_length=200)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=200)


class RoleOut(BaseModel):
    id: int
    name: str
    description: str
    is_superadmin: bool
    user_count: int = 0

    model_config = {"from_attributes": True}


class RolePermissionUpdate(BaseModel):
    permission_codes: list[str]


# ── Permission list ──

class PermissionOut(BaseModel):
    code: str
    name: str
    group_name: str

    model_config = {"from_attributes": True}
