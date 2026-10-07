"""终局 CI 缺口补测：Linux runner 上报的 3 个部分分支（99.99% → 100%）。

来源：1676530 的 backend-test 注解（TOTAL 39552 stmts / 9550 branch / 3 partial）：
- app/services/machine_code_service.py  260->266  内存段解析抛异常走兜底
- app/core/build_info.py                43->63    已有元数据时跳过 dev fallback
- app/api/v1/auth/auth.py               616->exit request.json() 返回非 dict

三处均可由平台无关的 mock 确定性覆盖（此前只在 Windows/本地路径上被间接覆盖，
Linux CI 组合下未命中）。
"""
from unittest.mock import MagicMock, patch

from app.api.v1.auth.auth import _revoke_request_tokens
from app.core import build_info as bi
from app.services.machine_code_service import MachineCodeService


def test_get_machine_info_memory_parse_exception():
    """CPU 成功、内存段 stdout=None → L260 解析抛 AttributeError 走内存段兜底（260->266）。"""
    cpu_result = MagicMock()
    cpu_result.stdout = "Intel Core\n"
    mem_result = MagicMock()
    mem_result.stdout = None  # None.strip() → AttributeError

    with patch("app.services.machine_code_service.platform") as mock_platform, patch(
        "app.services.machine_code_service.subprocess.run",
        side_effect=[cpu_result, mem_result],
    ):
        mock_platform.system.return_value = "Windows"
        mock_platform.release.return_value = "10"
        mock_platform.version.return_value = "10.0"
        mock_platform.machine.return_value = "x64"
        mock_platform.processor.return_value = ""
        mock_platform.node.return_value = "PC"
        info = MachineCodeService.get_machine_info()

    assert info["cpu_name"] == "Intel Core"
    assert "memory_gb" not in info  # 内存段异常被兜底，不写入字段且不影响响应


def test_get_machine_info_memory_empty_stdout():
    """内存段 stdout 为空白 → 解析为空串 → `if memory:` 假分支跳过赋值（260->266）。

    注意：Arc 260->266 不是异常路径（异常由 stdout=None 用例覆盖 259->263），
    而是空串时 if 为假直接落到 return info 的分支。
    """
    cpu_result = MagicMock()
    cpu_result.stdout = "Intel Core\n"
    mem_result = MagicMock()
    mem_result.stdout = "   \n"  # strip 后为空串

    with patch("app.services.machine_code_service.platform") as mock_platform, patch(
        "app.services.machine_code_service.subprocess.run",
        side_effect=[cpu_result, mem_result],
    ):
        mock_platform.system.return_value = "Windows"
        mock_platform.release.return_value = "10"
        mock_platform.version.return_value = "10.0"
        mock_platform.machine.return_value = "x64"
        mock_platform.processor.return_value = ""
        mock_platform.node.return_value = "PC"
        info = MachineCodeService.get_machine_info()

    assert info["cpu_name"] == "Intel Core"
    assert "memory_gb" not in info  # 空串 → 假分支 → 不写字段


def test_get_build_info_with_existing_metadata(monkeypatch):
    """_load 返回有效元数据 → 跳过 dev fallback 的 git 探测（43->63 假分支）。

    仓库检出目录没有 _ci_build_info.json 时，_load 恒为空 → 43 假分支在
    真实运行中从未被走到；此处显式注入有效元数据模拟「CI 注入过构建信息」。
    """
    monkeypatch.setattr(bi, "_cached", None)
    monkeypatch.setattr(
        bi,
        "_load",
        lambda: {"git_hash": "abc1234", "build_time": "2026-10-07T00:00:00", "builder": "ci"},
    )

    info = bi.get_build_info()

    assert info["git_hash"] == "abc1234"
    assert info["builder"] == "ci"
    assert info["version"]  # setdefault 补齐 PROJECT_VERSION
    assert bi.get_build_info() is info  # 第二次调用命中 _cached 快速返回


async def test_revoke_request_tokens_non_dict_body():
    """request.json() 返回非 dict（如列表）→ 跳过 refresh 吊销分支（616->exit）。"""

    class _ListBodyRequest:
        async def json(self):
            return []

    await _revoke_request_tokens(_ListBodyRequest(), None)

    class _BadJsonRequest:
        async def json(self):
            raise ValueError("invalid json body")

    # JSON 解析失败同样被兜底 except 吞掉，不影响吊销主流程
    await _revoke_request_tokens(_BadJsonRequest(), None)
