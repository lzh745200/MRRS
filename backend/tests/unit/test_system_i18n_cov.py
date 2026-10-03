"""app.api.v1.system.i18n 覆盖率攻坚测试

直接调用端点函数（async），覆盖全部 5 个端点的正常/异常分支。
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import app.api.v1.system.i18n as m


class TestGetSupportedLanguages:
    async def test_lists_three_languages(self):
        result = await m.get_supported_languages()
        assert result["success"] is True
        codes = [lang["code"] for lang in result["data"]]
        assert codes == ["zh-CN", "zh-TW", "en"]
        assert result["data"][0]["default"] is True


class TestGetTranslations:
    async def test_full_resource(self):
        result = await m.get_translations("zh-CN", namespace=None)
        assert result["success"] is True
        assert result["data"]["language"] == "zh-CN"
        assert result["data"]["total_keys"] == len(result["data"]["translations"])
        assert result["data"]["total_keys"] > 0

    async def test_namespace_filter(self):
        result = await m.get_translations("zh-CN", namespace="nav")
        translations = result["data"]["translations"]
        assert translations
        assert all(k.startswith("nav.") for k in translations)

    async def test_unsupported_language_400(self):
        with pytest.raises(HTTPException) as exc_info:
            await m.get_translations("fr")
        assert exc_info.value.status_code == 400
        assert "不支持的语言" in exc_info.value.detail


class TestTranslateKey:
    async def test_hit(self):
        result = await m.translate_key(key="nav.dashboard", language="zh-CN")
        assert result["data"]["value"] == "数据看板"
        assert result["data"]["fallback"] is False

    async def test_missing_key_falls_back_to_zh_cn(self):
        # en 资源中不存在的键 → 回退简体中文；zh-CN 也没有 → 返回键本身
        result = await m.translate_key(key="no.such.key", language="en")
        assert result["data"]["value"] == "no.such.key"
        assert result["data"]["fallback"] is True

    async def test_unsupported_language_400(self):
        with pytest.raises(HTTPException) as exc_info:
            await m.translate_key(key="nav.dashboard", language="fr")
        assert exc_info.value.status_code == 400


class TestGetMissingKeys:
    async def test_compare_zh_cn_vs_en(self):
        result = await m.get_missing_keys(
            source_lang="zh-CN", target_lang="en", current_user=MagicMock())
        data = result["data"]
        assert data["source_language"] == "zh-CN"
        assert data["missing_count"] == len(data["missing_keys"])
        assert 0 <= data["completion_rate"] <= 100
        # 公式守卫：完成率 = 源语言已被覆盖的键占比 = (|source| - |missing|) / |source|
        # （历史缺陷：误用 |target| - |missing|，target 少于 source 时严重低估）
        expected = round(
            (data["source_count"] - data["missing_count"]) / data["source_count"] * 100, 1
        )
        assert data["completion_rate"] == expected

    async def test_unsupported_source_400(self):
        with pytest.raises(HTTPException) as exc_info:
            await m.get_missing_keys(
                source_lang="fr", target_lang="en", current_user=MagicMock())
        assert exc_info.value.status_code == 400

    async def test_unsupported_target_400(self):
        with pytest.raises(HTTPException) as exc_info:
            await m.get_missing_keys(
                source_lang="zh-CN", target_lang="fr", current_user=MagicMock())
        assert exc_info.value.status_code == 400


class TestGetCurrentLanguage:
    async def test_default_zh_cn(self):
        result = await m.get_current_language(current_user=MagicMock())
        assert result["success"] is True
        assert result["data"]["language"] == "zh-CN"
