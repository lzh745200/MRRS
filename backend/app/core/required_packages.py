"""运行时依赖登记表（单一事实源）。

**为什么有本模块**（2026-09-14 修复）：依赖清单此前在 `app/main.py`、
`app/startup/environment.py`、`app/api/v1/system/env.py` **三处各写一份**且互相漂移：

- UI 那份列了应用**从不 import** 的 `fpdf2`（`requirements.txt` 里也没有该分发名）
  与**仅开发期**使用的 `pytest` —— 结果任何环境下都恒报"缺失依赖"，用户照提示
  `pip install fpdf2 pytest` 也永远装不出 `fpdf2`（幻影依赖）；
- 校验口径用 `importlib.metadata.distributions()` 枚举已安装分发，而 PyInstaller 冻结
  运行时里 bundled 包的 `.dist-info` 并不完整 —— 明明能 import 的包也被判缺失，
  安装包首启即误报"缺失 7 个依赖"。

**本模块统一的校验口径**：

1. 是否安装 → `importlib.util.find_spec(import 名)`（冻结运行时同样可靠）；
2. 版本号 → `importlib.metadata.version(分发名)` **尽力而为**，取不到不影响"已安装"判定；
3. 依赖分三级：运行时必需 / 运行时可选（缺了只降级个别功能）/ 仅开发期。

**新增依赖只改这里**，并在 `backend/requirements.txt`（或 `requirements-dev.txt`）登记同一分发名。
"""

from dataclasses import dataclass
from importlib import util as importlib_util
import sys
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Dependency:
    """一条依赖登记项。

    Attributes:
        distribution: PyPI 分发名（诊断/安装命令用，如 `python-docx`）
        module: import 名（校验用，如 `docx`）
        purpose: 用途（进日志与 UI，便于定位"缺了会怎样"）
        requirements: 应登记在哪份依赖清单里
    """

    distribution: str
    module: str
    purpose: str
    requirements: str = "requirements.txt"


# ── 运行时必需：缺任何一个系统都不可用（启动自检即阻断级告警）──
REQUIRED_RUNTIME_PACKAGES: Tuple[Dependency, ...] = (
    Dependency("fastapi", "fastapi", "HTTP 框架（应用入口）"),
    Dependency("uvicorn", "uvicorn", "ASGI 服务器"),
    Dependency("sqlalchemy", "sqlalchemy", "ORM 与数据库访问"),
    Dependency("pydantic", "pydantic", "请求/响应数据校验"),
    Dependency("pandas", "pandas", "报表与数据分析"),
    Dependency("openpyxl", "openpyxl", "Excel 导入导出"),
)

# ── 运行时可选：缺失只影响对应导出/图片功能，不影响系统启动 ──
OPTIONAL_RUNTIME_PACKAGES: Tuple[Dependency, ...] = (
    Dependency("reportlab", "reportlab", "PDF 导出"),
    Dependency("python-docx", "docx", "Word 导出"),
    Dependency("pillow", "PIL", "头像与图片处理"),
)

# ── 仅开发/测试期：不得计入运行时缺失（生产/安装包里本就没有）──
DEV_ONLY_PACKAGES: Tuple[Dependency, ...] = (
    Dependency("pytest", "pytest", "自动化测试", "requirements-dev.txt"),
    Dependency("flake8", "flake8", "静态检查", "requirements-dev.txt"),
    Dependency("bandit", "bandit", "安全扫描", "requirements-dev.txt"),
)


def is_importable(module: str) -> bool:
    """模块是否可导入（find_spec 口径：冻结运行时同样可靠）。"""
    try:
        return importlib_util.find_spec(module) is not None
    except (ImportError, ValueError):  # pragma: no cover - find_spec 对坏包极少数会抛
        return False


def installed_version(distribution: str) -> Optional[str]:
    """分发版本号（尽力而为：冻结运行时可能查不到，返回 None 不代表未安装）。"""
    try:
        from importlib.metadata import version

        return version(distribution)
    except Exception:  # pragma: no cover - 元数据损坏/缺失时静默降级
        return None


def describe(dependencies: Sequence[Dependency]) -> List[Dict[str, object]]:
    """把登记项展开为可序列化清单（分发名/import 名/用途/是否安装/版本）。"""
    items: List[Dict[str, object]] = []
    for dep in dependencies:
        ok = is_importable(dep.module)
        items.append({
            "distribution": dep.distribution,
            "module": dep.module,
            "purpose": dep.purpose,
            "requirements": dep.requirements,
            "installed": ok,
            "version": installed_version(dep.distribution) if ok else None,
        })
    return items


def missing(dependencies: Sequence[Dependency]) -> List[Dependency]:
    """登记项中不可导入的那些。"""
    return [dep for dep in dependencies if not is_importable(dep.module)]


def missing_runtime() -> List[Dependency]:
    """运行时必需但缺失的依赖。"""
    return missing(REQUIRED_RUNTIME_PACKAGES)


def missing_optional() -> List[Dependency]:
    """运行时可选但缺失的依赖（功能降级提示）。"""
    return missing(OPTIONAL_RUNTIME_PACKAGES)


def missing_dev() -> List[Dependency]:
    """仅开发期依赖的缺失情况（开发环境诊断用）。"""
    return missing(DEV_ONLY_PACKAGES)


def is_frozen() -> bool:
    """是否运行在 PyInstaller 冻结运行时（安装包自包含，pip 不适用）。"""
    return bool(getattr(sys, "frozen", False))


def fix_command(missing_deps: Sequence[Dependency], frozen: Optional[bool] = None) -> Optional[str]:
    """给出可执行的修复命令；冻结运行时返回 None（自包含运行时无 pip 可装）。

    Returns:
        形如 `"<当前解释器>" -m pip install -r "<requirements.txt 绝对路径>"`；
        无缺失、或冻结运行时、或找不到依赖清单文件时返回 None。
    """
    if not missing_deps:
        return None
    if frozen is None:
        frozen = is_frozen()
    if frozen:
        return None

    from pathlib import Path

    # 本模块位于 backend/app/core/，requirements*.txt 在 backend/ 下
    backend_dir = Path(__file__).resolve().parent.parent.parent
    files = sorted({dep.requirements for dep in missing_deps})
    parts = []
    for name in files:
        path = backend_dir / name
        if path.exists():
            parts.append(f'"{sys.executable}" -m pip install -r "{path}"')
    if parts:
        return " && ".join(parts)
    # 依赖清单缺失（非常规部署）：退化为按分发名安装，至少让提示可用
    names = " ".join(sorted({dep.distribution for dep in missing_deps}))
    return f'"{sys.executable}" -m pip install {names}'
