"""瓦片包导入的请求体上限回归测试。

背景（2026-10-24 现场反馈）：在「系统管理 → 地图瓦片 → 导入瓦片包」上传市州包
（7~17MB）或全省包（59MB）时被中间件拒绝：
`上传内容超过大小限制 (10MB)，请拆分或压缩后重试`。

根因：`_resolve_body_limit` 对 multipart 请求只在路径命中
`LARGE_PAYLOAD_PATH_PREFIXES` 时才采用分级上限；`/api/v1/map/tiles/import`
此前既不在该白名单、也没有 `MULTIPART_BODY_LIMITS` 条目，于是被
`min(DEFAULT_MULTIPART_BODY_LIMIT, max_body_size)` 收紧到全局 10MB。

本测试锁定修复后的契约：
- `/api/v1/map/tiles/import` 的 multipart 上限 = 512MB（对齐服务层 MAX_TILE_UPLOAD_BYTES）；
- 该路径的非 multipart 请求仍只允许全局 10MB（不放开 JSON 面）；
- 未登记路径伪造 multipart 仍收紧到 10MB（原有反绕过策略不退化）。
"""

from types import SimpleNamespace

from app.middleware.body_size_limit import (
    DEFAULT_MULTIPART_BODY_LIMIT,
    MULTIPART_BODY_LIMITS,
    _multipart_limit_for,
    _resolve_body_limit,
)

TEN_MB = 10 * 1024 * 1024
MAX_UPLOAD = 512 * 1024 * 1024


def _request(path: str, content_type: str):
    """够用的 Request 替身：`_resolve_body_limit` 只读 url.path 与 content-type。"""
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        headers={"content-type": content_type},
    )


class TestMapTilesImportLimit:
    def test_multipart_tiles_import_allows_512mb(self):
        """市州包/全省包（7~59MB）必须能通过中间件，而不是被 10MB 拦住。"""
        limit = _resolve_body_limit(
            _request("/api/v1/map/tiles/import", "multipart/form-data; boundary=abc"), TEN_MB
        )
        assert limit == MAX_UPLOAD

    def test_tiles_prefix_covers_import_endpoint(self):
        """前缀登记必须真正覆盖 /map/tiles/import（防止后续改路径名而失效）。"""
        assert _multipart_limit_for("/api/v1/map/tiles/import") == MAX_UPLOAD
        assert ("/api/v1/map/tiles", MAX_UPLOAD) in MULTIPART_BODY_LIMITS

    def test_non_multipart_tiles_import_stays_10mb(self):
        """只放宽 multipart；JSON 面仍受全局 10MB 约束。"""
        limit = _resolve_body_limit(
            _request("/api/v1/map/tiles/import", "application/json"), TEN_MB
        )
        assert limit == TEN_MB

    def test_unregistered_path_with_fake_multipart_still_10mb(self):
        """未登记路径伪造 multipart 头 → 仍收紧到 10MB（反绕过策略不退化）。"""
        limit = _resolve_body_limit(
            _request("/api/v1/dashboard", "multipart/form-data; boundary=abc"), TEN_MB
        )
        assert limit == TEN_MB

    def test_registered_upload_path_keeps_its_own_limit(self):
        """已有的分级上限不受本次改动影响（备份恢复仍是 10GB）。"""
        assert (
            _resolve_body_limit(
                _request("/api/v1/system/backup/restore", "multipart/form-data; boundary=b"), TEN_MB
            )
            == 10 * 1024 * 1024 * 1024
        )

    def test_default_multipart_limit_unchanged(self):
        """默认 multipart 上限保持 512MB。"""
        assert DEFAULT_MULTIPART_BODY_LIMIT == MAX_UPLOAD
