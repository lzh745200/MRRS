"""全局常量定义。

消除跨层导入：调度层不应依赖 HTTP API 层的模块级常量。
所有跨层共享的常量定义在此。
"""

# ── 数据分析 ──
# 数据分析缓存前缀（原在 app.api.v1.data.data.analytics 中定义）
ANALYTICS_CACHE_PREFIX = "analytics:"

# ── 分页 ──
DEFAULT_PAGE_SIZE = 20
# 分页**硬上限**（2026-10-25 由 100 上调为 200）：
#   1) 前端已有 21 处 `page_size: 200`（地图/帮扶村/转交人搜索等"取一屏全量"场景），
#      上限若为 100，这些调用会直接 422 —— 等于用一个门禁制造一批线上故障；
#   2) 200 是本仓既有的**事实上限**：18 处端点本来就写 `le=200`；
#   3) 仍需上限的原因：离线单机里 `page_size=1000` 会一次实例化上千 ORM 对象
#      （含加密 PII 列），Electron 侧拿到超大 JSON 会卡死，现场表现是"点一下列表白屏"。
# 任何新的分页参数必须写 `Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)`，
# 由 backend/scripts/check_pagination_cap.py 门禁保证。
MAX_PAGE_SIZE = 200

# ── HTTP ──
# Nginx 非标准状态码：客户端在服务器完成响应前关闭了连接
HTTP_CLIENT_CLOSED_REQUEST = 499

# ── 出厂凭据 ──
# 默认管理员出厂密码（单一来源）：main.py 种子逻辑与 machine_code.py 破窗恢复
# 端点共同引用。保密部署可通过 DEFAULT_ADMIN_PASSWORD 环境变量覆盖种子值，
# 但出厂恢复端点固定重置为本常量（首登强制改密，不构成弱口令驻留）。
# 2026-10-06：由 "Admin@2026"（10 位，低于 PasswordPolicy.MIN_LENGTH=12 且可被
# 字典猜测）改为 13 位混合字符，满足自身密码策略；配套由 core/security.py 的
# get_current_user 在服务端强制首登改密（原先仅前端路由守卫拦截，直连 API 可绕过）。
FACTORY_ADMIN_USERNAME = "admin"
FACTORY_ADMIN_PASSWORD = "zgcZGC733035#"


# ── 角色常量 ──
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_VIEWER = "viewer"

# 兼容的历史角色值（已精简合并）：approval_leader/manager 并入 admin，operator 并入 user
ROLE_APPROVAL_LEADER = "approval_leader"
ROLE_MANAGER = "manager"
ROLE_OPERATOR = "operator"

ADMIN_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN}

# 精简后的实用角色（用户可选择的角色）
PRACTICAL_ROLES = [
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_USER,
    ROLE_VIEWER,
]

# 全部合法角色集合（精简后仅 4 个实用角色；
# 历史角色值由 normalize_role() 在入口处归一化，不再作为合法值）
ALL_ROLES = list(PRACTICAL_ROLES)

# 旧角色值 → 新角色值的归一化映射（approval_leader/manager 视为管理员级，operator 视为普通用户）
_ROLE_NORMALIZE_MAP = {
    ROLE_APPROVAL_LEADER: ROLE_ADMIN,
    ROLE_MANAGER: ROLE_ADMIN,
    ROLE_OPERATOR: ROLE_USER,
}


def normalize_role(role) -> str:
    """归一化角色值：旧角色映射到精简后的角色，未知值原样返回（由调用方校验）。

    Args:
        role: 角色值（可为 None）

    Returns:
        str: 归一化后的角色；未知角色原样返回以便校验层拒绝
    """
    if not role:
        return ROLE_USER
    role_str = str(role)
    if role_str in _ROLE_NORMALIZE_MAP:
        return _ROLE_NORMALIZE_MAP[role_str]
    return role_str


class UserRole:
    """用户角色枚举（字符串常量）"""
    SUPER_ADMIN = ROLE_SUPER_ADMIN
    ADMIN = ROLE_ADMIN
    USER = ROLE_USER
    VIEWER = ROLE_VIEWER
    # 兼容历史角色值
    APPROVAL_LEADER = ROLE_APPROVAL_LEADER
    MANAGER = ROLE_MANAGER
    OPERATOR = ROLE_OPERATOR
