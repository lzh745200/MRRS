"""认证相关 Pydantic Schemas"""

import json
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码")


class Token(BaseModel):
    """令牌"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")


class TokenPayload(BaseModel):
    """令牌载荷"""

    sub: Optional[str] = None


class UserInfo(BaseModel):
    """用户基本信息"""

    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: Optional[str] = Field(None, description="邮箱")
    full_name: Optional[str] = Field(None, description="姓名")
    role: Optional[str] = Field(None, description="角色")
    is_active: bool = Field(default=True, description="是否激活")
    is_superuser: bool = Field(default=False, description="是否超级管理员")
    organization_id: Optional[int] = Field(None, description="所属组织ID")
    organization_name: Optional[str] = Field(None, description="所属组织名称")
    permissions: Optional[list] = Field(default_factory=list, description="权限列表")
    allowed_menus: Optional[list] = Field(None, description="允许访问的菜单列表")
    allowed_menus_list: Optional[list] = Field(None, description="允许访问的菜单key列表")

    @field_validator("allowed_menus", "allowed_menus_list", mode="before")
    @classmethod
    def _normalize_menu_keys(cls, value):
        """DB 的 users.allowed_menus 是 JSON 文本；响应契约要求数组。

        真实模型通过 ``allowed_menus_list`` 属性已解析，但历史调用方/外部数据
        仍可能直接传原始字符串。这里统一把 JSON 数组文本转成 list，避免
        Pydantic 抛 ``list_type``（前端看到「allowed_menus应为数组」）。
        非法 JSON 按“未配置”处理，不把坏数据带进出站响应。
        """
        if not isinstance(value, str):
            return value
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
        return parsed if isinstance(parsed, list) else None


class LoginData(BaseModel):
    """登录数据（token + user）"""

    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: Optional[UserInfo] = Field(None, description="用户信息")


class LoginResponse(BaseModel):
    """登录响应"""

    code: int = Field(default=200, description="状态码")
    data: Optional[LoginData] = Field(None, description="登录数据")
    message: str = Field(default="", description="消息")
    must_change_password: bool = Field(default=False, description="是否必须修改密码")
    refresh_token: Optional[str] = Field(None, description="刷新令牌")
    two_factor_required: bool = Field(default=False, description="是否需要双因素认证")
    temp_token: Optional[str] = Field(None, description="2FA临时令牌（用于验证TOTP后换取正式令牌）")


class TwoFactorLoginVerifyRequest(BaseModel):
    """2FA登录验证请求"""

    temp_token: str = Field(..., description="登录时返回的临时令牌")
    code: str = Field(..., min_length=6, max_length=8, description="TOTP验证码或备用码")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=12, description="新密码，至少12位")
