"""app/utils/paths.py 单元测试。

覆盖所有路径函数的平台/环境分支与安全检查（_safe_join 路径遍历防护）。
通过 monkeypatch 控制 sys.frozen / platform.system / 环境变量 / Path.home / cwd，
绝不用 patch.dict(os.environ, clear=True)。
"""
import platform
import sys
from pathlib import Path

import pytest

from app.utils import paths as paths_module
from app.utils.paths import (
    PathTraversalError,
    _safe_join,
    db_file_from_url,
    get_app_data_dir,
    get_backup_directory,
    get_backup_path,
    get_cache_path,
    get_database_path,
    get_data_path,
    get_log_path,
    get_project_backend_dir,
    get_runtime_uploads_path,
    get_uploads_path,
    is_bundled,
    is_linux,
)


# 本模块专测 paths.py 的解析逻辑：多处断言 get_app_data_dir() 等于真实的
# get_project_backend_dir()（或断言其 .name == "backend"）。conftest 的
# _isolate_app_data_dir autouse fixture 会把该函数 patch 成会话临时目录，
# 与这些断言直接冲突，故整模块豁免。需要临时目录的测试在下方各自 monkeypatch。
pytestmark = pytest.mark.real_backend_dir


def _backend_dir_url(path: Path) -> str:
    """把本地绝对路径转成 sqlite:/// URL（Windows 反斜杠转正斜杠）。"""
    return "sqlite:///" + str(path).replace("\\", "/")


# ── 公共 fixture：每次测试前清理"打包态"属性 ──
@pytest.fixture(autouse=True)
def _clear_bundled_attrs(monkeypatch):
    """每个测试默认清除 sys.frozen / sys._MEIPASS，保证 is_bundled() 默认 False。"""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)


# ─────────────────────────────────────────────────────────────
# _safe_join
# ─────────────────────────────────────────────────────────────
class TestSafeJoin:
    def test_empty_sub_path_returns_base_unchanged(self, tmp_path):
        assert _safe_join(tmp_path, "") == tmp_path

    def test_valid_sub_path_resolves_within_base(self, tmp_path):
        result = _safe_join(tmp_path, "subdir/file.txt")
        assert result == (tmp_path / "subdir" / "file.txt").resolve()
        # 仍在 base 内
        assert str(result).startswith(str(tmp_path.resolve()))

    def test_valid_sub_path_with_nested_dirs(self, tmp_path):
        result = _safe_join(tmp_path, "a/b/c/d.txt")
        assert result.parent == (tmp_path / "a" / "b" / "c").resolve()

    def test_traversal_outside_base_raises(self, tmp_path):
        with pytest.raises(PathTraversalError) as exc:
            _safe_join(tmp_path, "../escape.txt")
        assert "路径遍历被拒绝" in str(exc.value)
        assert "../escape.txt" in str(exc.value)

    def test_traversal_deep_outside_base_raises(self, tmp_path):
        with pytest.raises(PathTraversalError):
            _safe_join(tmp_path, "a/../../../escape")

    def test_traversal_error_is_value_error_subclass(self):
        assert issubclass(PathTraversalError, ValueError)


# ─────────────────────────────────────────────────────────────
# is_bundled / is_linux
# ─────────────────────────────────────────────────────────────
class TestPlatformHelpers:
    def test_is_bundled_false_by_default(self):
        assert is_bundled() is False

    def test_is_bundled_true_when_frozen_with_meipass(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake/meipass", raising=False)
        assert is_bundled() is True

    def test_is_bundled_true_when_frozen_without_meipass(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        # _MEIPASS 已被 autouse fixture 删除；onedir 模式 frozen 但无 _MEIPASS 仍判定为打包环境
        assert is_bundled() is True

    def test_is_linux_true(self, monkeypatch):
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        assert is_linux() is True

    def test_is_linux_false_on_windows(self, monkeypatch):
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        assert is_linux() is False

    def test_is_linux_false_on_darwin(self, monkeypatch):
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        assert is_linux() is False


# ─────────────────────────────────────────────────────────────
# get_app_data_dir —— 所有平台/环境分支
# ─────────────────────────────────────────────────────────────
class TestGetAppDataDir:
    def test_dev_windows_uses_backend_dir(self, monkeypatch, tmp_path):
        """开发环境（Windows、非打包）数据根 = get_project_backend_dir()，与 CWD 无关。"""
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        monkeypatch.setattr(paths_module, "get_project_backend_dir", lambda: tmp_path)
        # 即便 chdir 到别处，也应返回被 patch 的 backend 根（tmp_path），证明不依赖 CWD
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        result = get_app_data_dir()
        assert result == tmp_path

    def test_dev_linux_with_dev_mode_uses_backend_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        monkeypatch.setenv("BUMOFU_DEV_MODE", "1")
        monkeypatch.setattr(paths_module, "get_project_backend_dir", lambda: tmp_path)
        assert get_app_data_dir() == tmp_path

    def test_dev_uses_real_backend_dir_not_cwd(self, monkeypatch, tmp_path):
        """核心回归（任务#6 风险1）：dev 分支返回真实 get_project_backend_dir()，
        即使 chdir 到 tmp_path 也不变——证明数据根不再受 CWD 影响。"""
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        real_backend = get_project_backend_dir()
        monkeypatch.chdir(tmp_path)
        result = get_app_data_dir()
        assert result == real_backend
        assert result != tmp_path

    def test_prod_linux_without_dev_mode_uses_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        monkeypatch.delenv("BUMOFU_DEV_MODE", raising=False)
        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        result = get_app_data_dir()
        assert result == fake_home / ".bumofu"
        assert result.exists()

    def test_project_backend_dir_env_override_direct(self, monkeypatch, tmp_path):
        """BUMOFU_BACKEND_DIR_OVERRIDE 在调用时生效（W1 不变量 #11 的机制本体）。

        Windows 开发路径 get_app_data_dir() 走 else 分支间接覆盖 override 行；
        Linux 生产路径 get_app_data_dir 提前返回 ~/.bumofu、根本不经过
        get_project_backend_dir —— CI(Linux) 上 override 分支恒缺 1 行导致
        fail_under=100 门禁红（2026-09-05 PR Checks 实测）。此处直接调用锁定。
        """
        monkeypatch.setenv("BUMOFU_BACKEND_DIR_OVERRIDE", str(tmp_path))
        assert get_project_backend_dir() == tmp_path
        # 未设置时回退到仓库 backend 目录（.name == "backend"）
        monkeypatch.delenv("BUMOFU_BACKEND_DIR_OVERRIDE")
        assert get_project_backend_dir().name == "backend"

    def test_bundled_linux_uses_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        result = get_app_data_dir()
        assert result == fake_home / ".bumofu"

    def test_bundled_windows_with_localappdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        local = tmp_path / "local"
        monkeypatch.setenv("LOCALAPPDATA", str(local))
        monkeypatch.delenv("APPDATA", raising=False)
        result = get_app_data_dir()
        assert result == local / "bumofu-assistance"

    def test_bundled_windows_appdata_fallback_when_no_localappdata(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        roaming = tmp_path / "roaming"
        monkeypatch.setenv("APPDATA", str(roaming))
        result = get_app_data_dir()
        assert result == roaming / "bumofu-assistance"

    def test_bundled_windows_no_env_uses_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)
        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        result = get_app_data_dir()
        assert result == fake_home / ".bumofu"

    def test_directory_is_created(self, monkeypatch, tmp_path):
        """无论走哪个分支，最终目录必须存在（此处验证 dev 分支会 mkdir）。"""
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        fake_backend = tmp_path / "backend_root"
        monkeypatch.setattr(
            paths_module, "get_project_backend_dir", lambda: fake_backend
        )
        assert not fake_backend.exists()
        result = get_app_data_dir()
        assert result == fake_backend
        assert result.exists()
        assert result.is_dir()


# ─────────────────────────────────────────────────────────────
# 通用辅助：在 dev mode 下测试各路径函数
# ─────────────────────────────────────────────────────────────
def _setup_dev_mode(monkeypatch, tmp_path):
    """统一设置 dev mode（Windows 开发环境 + 数据根隔离到 tmp_path）。

    任务#16：paths.py 已把开发/测试分支的数据根从 ``Path.cwd()`` 改为
    ``get_project_backend_dir()``（基于 ``__file__`` 的固定 backend 目录，与
    CWD 无关）。因此单纯 ``monkeypatch.chdir(tmp_path)`` 不再影响返回值，反而
    会让测试写入真实 backend/data、backend/uploads 目录，破坏逐用例文件系统
    隔离并污染其他测试（test_recycle_bin 全量顺序运行偶发失败的根因之一）。
    改为显式 monkeypatch ``get_project_backend_dir`` 返回 ``tmp_path``：既恢复
    逐用例隔离（所有派生路径落在 tmp_path 内），又保留原有 tmp_path 断言语义。
    """
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(paths_module, "get_project_backend_dir", lambda: tmp_path)


# ─────────────────────────────────────────────────────────────
# get_data_path
# ─────────────────────────────────────────────────────────────
class TestGetDataPath:
    def test_empty_sub_path_returns_base(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_data_path("")
        assert result == tmp_path / "data"

    def test_default_arg_returns_base(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_data_path()
        assert result == tmp_path / "data"

    def test_flat_filename_parent_equals_base_no_mkdir(
        self, monkeypatch, tmp_path
    ):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_data_path("file.db")
        assert result == (tmp_path / "data" / "file.db").resolve()
        # base 目录由 get_app_data_dir 创建；data 目录不应被本函数创建
        # 但 file.db 的父目录是 data，等价于 base —— 不应抛错

    def test_nested_sub_path_creates_parent_dirs(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_data_path("subdir/deep/file.txt")
        assert result.parent.exists()
        assert result.parent == (tmp_path / "data" / "subdir" / "deep").resolve()

    def test_traversal_raises(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        with pytest.raises(PathTraversalError):
            get_data_path("../../escape")


# ─────────────────────────────────────────────────────────────
# get_backup_path / get_backup_directory
# ─────────────────────────────────────────────────────────────
class TestGetBackupPath:
    def test_empty_sub_path_returns_base(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        assert get_backup_path("") == tmp_path / "backups"

    def test_default_arg_returns_base(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        assert get_backup_path() == tmp_path / "backups"

    def test_flat_filename_returns_path(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_backup_path("backup.zip")
        assert result == (tmp_path / "backups" / "backup.zip").resolve()

    def test_nested_sub_path_creates_parent(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_backup_path("daily/2025/backup.zip")
        assert result.parent.exists()

    def test_traversal_raises(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        with pytest.raises(PathTraversalError):
            get_backup_path("../escape")


class TestBackupDirectoryAlias:
    def test_alias_is_same_function(self):
        assert get_backup_directory is get_backup_path

    def test_alias_returns_same_result(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        assert get_backup_directory("x.zip") == get_backup_path("x.zip")


# ─────────────────────────────────────────────────────────────
# get_cache_path —— 包含独立的平台分支
# ─────────────────────────────────────────────────────────────
class TestGetCachePath:
    def test_dev_mode_empty_returns_data_cache(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        assert get_cache_path("") == tmp_path / "data" / "cache"

    def test_dev_mode_with_sub_path(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_cache_path("tmp.json")
        assert result == (tmp_path / "data" / "cache" / "tmp.json").resolve()

    def test_dev_mode_nested_creates_parent(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_cache_path("sub/dir/cache.json")
        assert result.parent.exists()

    def test_dev_mode_traversal_raises(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        with pytest.raises(PathTraversalError):
            get_cache_path("../escape")

    def test_bundled_linux_uses_home_cache(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        assert get_cache_path("") == fake_home / ".bumofu" / "cache"

    def test_bundled_linux_with_sub_path(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        result = get_cache_path("a/b.json")
        assert result == (fake_home / ".bumofu" / "cache" / "a" / "b.json").resolve()

    def test_bundled_windows_with_localappdata(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        local = tmp_path / "local"
        monkeypatch.setenv("LOCALAPPDATA", str(local))
        monkeypatch.delenv("APPDATA", raising=False)
        assert get_cache_path("") == local / "bumofu-assistance" / "cache"

    def test_bundled_windows_appdata_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        roaming = tmp_path / "roaming"
        monkeypatch.setenv("APPDATA", str(roaming))
        assert get_cache_path("") == roaming / "bumofu-assistance" / "cache"

    def test_bundled_windows_no_env_uses_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/fake", raising=False)
        monkeypatch.setattr(platform, "system", lambda: "Windows")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)
        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        assert get_cache_path("") == fake_home / ".bumofu" / "cache"

    def test_prod_linux_without_dev_mode_uses_home_cache(
        self, monkeypatch, tmp_path
    ):
        """非 bundled 但 Linux 生产（无 BUMOFU_DEV_MODE）也走 home 分支。"""
        monkeypatch.setattr(platform, "system", lambda: "Linux")
        monkeypatch.delenv("BUMOFU_DEV_MODE", raising=False)
        fake_home = tmp_path / "home"
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        assert get_cache_path("") == fake_home / ".bumofu" / "cache"


# ─────────────────────────────────────────────────────────────
# get_uploads_path
# ─────────────────────────────────────────────────────────────
class TestGetUploadsPath:
    def test_empty_returns_base(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        assert get_uploads_path("") == tmp_path / "uploads"

    def test_default_arg_returns_base(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        assert get_uploads_path() == tmp_path / "uploads"

    def test_flat_filename(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_uploads_path("avatar.png")
        assert result == (tmp_path / "uploads" / "avatar.png").resolve()

    def test_nested_creates_parent(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_uploads_path("users/123/avatar.png")
        assert result.parent.exists()

    def test_traversal_raises(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        with pytest.raises(PathTraversalError):
            get_uploads_path("../escape")


# ─────────────────────────────────────────────────────────────
# get_database_path
# ─────────────────────────────────────────────────────────────
class TestGetDatabasePath:
    def test_returns_data_path_with_db_filename(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_database_path()
        assert result == (tmp_path / "data" / "rural_revitalization.db").resolve()


# ─────────────────────────────────────────────────────────────
# get_log_path —— 总是创建 base 目录
# ─────────────────────────────────────────────────────────────
class TestGetLogPath:
    def test_empty_returns_base_and_creates_dir(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_log_path("")
        assert result == tmp_path / "logs"
        assert result.exists()
        assert result.is_dir()

    def test_default_arg_returns_base(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        assert get_log_path() == tmp_path / "logs"

    def test_with_sub_path_returns_file_path(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_log_path("app.log")
        assert result == (tmp_path / "logs" / "app.log").resolve()
        # base 应被创建
        assert (tmp_path / "logs").exists()

    def test_nested_sub_path_creates_parents(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        result = get_log_path("subdir/run.log")
        assert result.parent.exists()

    def test_traversal_raises(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        with pytest.raises(PathTraversalError):
            get_log_path("../../escape")


# ─────────────────────────────────────────
# get_project_backend_dir —— 任务#6 新增的 CWD-无关固定根（覆盖率补充）
# ─────────────────────────────────────────
class TestGetProjectBackendDir:
    def test_returns_backend_dir_from_file_location(self):
        """基于 paths.py 的 __file__ 上溯三级 = backend 根目录。"""
        result = get_project_backend_dir()
        assert result == Path(paths_module.__file__).resolve().parents[2]
        assert result.name == "backend"
        assert (result / "app" / "utils" / "paths.py").exists()

    def test_is_cwd_independent(self, monkeypatch, tmp_path):
        """核心回归：无论 CWD 在哪，都返回固定 backend 目录（任务#6 风险1修复）。"""
        expected = get_project_backend_dir()
        monkeypatch.chdir(tmp_path)
        assert get_project_backend_dir() == expected
        assert get_project_backend_dir() != tmp_path


# ─────────────────────────────────────────
# db_file_from_url —— 所有分支（覆盖率补充）
# ─────────────────────────────────────────
class TestDbFileFromUrl:
    def test_empty_returns_none(self):
        assert db_file_from_url("") is None

    def test_non_sqlite_returns_none(self):
        assert db_file_from_url("postgresql://localhost/x") is None

    def test_sqlite_without_triple_slash_returns_none(self):
        # 以 sqlite 开头但不是 sqlite:/// 前缀
        assert db_file_from_url("sqlite://x") is None

    def test_memory_returns_none(self):
        assert db_file_from_url("sqlite:///:memory:") is None

    def test_empty_raw_returns_none(self):
        assert db_file_from_url("sqlite:///") is None

    def test_relative_returns_none(self):
        assert db_file_from_url("sqlite:///./test.db") is None

    def test_absolute_returns_path(self, tmp_path):
        target = tmp_path / "x.db"
        assert db_file_from_url(_backend_dir_url(target)) == target

    def test_query_string_stripped(self, tmp_path):
        target = tmp_path / "x.db"
        url = _backend_dir_url(target) + "?check_same_thread=false"
        assert db_file_from_url(url) == target

    def test_url_encoded_path_decoded(self, tmp_path):
        from urllib.parse import quote

        target = tmp_path / "my db.sqlite"
        url = "sqlite:///" + quote(str(target).replace("\\", "/"))
        assert db_file_from_url(url) == target


# ─────────────────────────────────────────
# get_database_path —— env / settings / 异常兑底分支（覆盖率补充）
# ─────────────────────────────────────────
class TestGetDatabasePathBranches:
    def test_env_absolute_url_used(self, monkeypatch, tmp_path):
        dbfile = tmp_path / "envdb.sqlite"
        monkeypatch.setenv("DATABASE_URL", _backend_dir_url(dbfile))
        result = get_database_path()
        assert result == dbfile
        assert result.parent.exists()

    def test_settings_url_used_when_env_empty(self, monkeypatch, tmp_path):
        from app.core.config import settings

        monkeypatch.delenv("DATABASE_URL", raising=False)
        dbfile = tmp_path / "settings.sqlite"
        monkeypatch.setattr(
            settings, "DATABASE_URL", _backend_dir_url(dbfile), raising=False
        )
        assert get_database_path() == dbfile

    def test_settings_import_error_falls_back(self, monkeypatch, tmp_path):
        """DATABASE_URL env 为空 + settings 导入报错 → 兑底传统推断路径。"""
        _setup_dev_mode(monkeypatch, tmp_path)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # sys.modules 中置 None 会使 ``from app.core.config import settings`` 抛 ImportError
        monkeypatch.setitem(sys.modules, "app.core.config", None)
        result = get_database_path()
        assert result == (tmp_path / "data" / "rural_revitalization.db").resolve()


# ─────────────────────────────────────────
# get_runtime_uploads_path —— env / settings / 兑底 / 子路径分支（覆盖率补充）
# ─────────────────────────────────────────
class TestGetRuntimeUploadsPath:
    def test_env_absolute_used(self, monkeypatch, tmp_path):
        up = tmp_path / "envuploads"
        monkeypatch.setenv("UPLOAD_DIR", str(up))
        assert get_runtime_uploads_path() == up

    def test_env_relative_falls_back_to_uploads(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        monkeypatch.setenv("UPLOAD_DIR", "relative_uploads")
        assert get_runtime_uploads_path() == tmp_path / "uploads"

    def test_no_env_uses_settings_absolute(self, monkeypatch, tmp_path):
        from app.core.config import settings

        monkeypatch.delenv("UPLOAD_DIR", raising=False)
        up = tmp_path / "setuploads"
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(up), raising=False)
        assert get_runtime_uploads_path() == up

    def test_settings_import_error_falls_back(self, monkeypatch, tmp_path):
        _setup_dev_mode(monkeypatch, tmp_path)
        monkeypatch.delenv("UPLOAD_DIR", raising=False)
        monkeypatch.setitem(sys.modules, "app.core.config", None)
        assert get_runtime_uploads_path() == tmp_path / "uploads"

    def test_sub_path_flat_no_extra_mkdir(self, monkeypatch, tmp_path):
        up = tmp_path / "envuploads_flat"
        monkeypatch.setenv("UPLOAD_DIR", str(up))
        result = get_runtime_uploads_path("avatar.png")
        assert result == (up / "avatar.png").resolve()

    def test_sub_path_nested_creates_parent(self, monkeypatch, tmp_path):
        up = tmp_path / "envuploads_nested"
        monkeypatch.setenv("UPLOAD_DIR", str(up))
        result = get_runtime_uploads_path("users/1/avatar.png")
        assert result == (up / "users" / "1" / "avatar.png").resolve()
        assert result.parent.exists()

    def test_sub_path_traversal_raises(self, monkeypatch, tmp_path):
        up = tmp_path / "envuploads_trav"
        monkeypatch.setenv("UPLOAD_DIR", str(up))
        with pytest.raises(PathTraversalError):
            get_runtime_uploads_path("../escape")
