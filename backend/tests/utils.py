"""Shared test utilities.

W4-T3（2026-09-30）：原 `HTTP_SUCCESS_OR_ERROR = (200, 201, 400, 401, 403, 404, 422, 500)`
与 `assert_create_or_error()` 是典型的**弱断言**——把 500 与成功码并列，任何 5xx 回归都能
让测试变绿；12 个调用点已全部改为精确断言（管理员 200 / 越权 401-403 / 健康检查 200）。
这里保留一个**只排除 5xx** 的守卫供新测试表达"不崩即可"的中间态，但优先使用精确断言。
"""

from typing import Tuple

# 明确排除 5xx：任何服务端错误都必须让测试失败
NON_SERVER_ERROR: Tuple[int, ...] = (200, 201, 202, 204, 400, 401, 403, 404, 405, 409, 422, 429)


def assert_no_server_error(status_code: int) -> None:
    """断言响应不是服务端错误（5xx）。

    Args:
        status_code: HTTP 响应码。

    Raises:
        AssertionError: 5xx 或未预期的状态码。
    """
    assert status_code in NON_SERVER_ERROR, (
        f"服务端错误或未预期状态 {status_code}（5xx 一律视为失败）"
    )
