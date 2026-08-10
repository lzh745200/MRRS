"""
国际化API
提供系统多语言支持和翻译资源管理
支持中文（简体）、中文（繁体）、英文等语言切换
"""

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/i18n", tags=["国际化"])


# ==================== 内置翻译资源 ====================

# 中文（简体）翻译资源
_ZH_CN_TRANSLATIONS: Dict[str, str] = {
    "app.title": "帮扶管理信息系统",
    "app.subtitle": "助力乡村振兴战略实施",
    "nav.dashboard": "数据看板",
    "nav.villages": "帮扶村管理",
    "nav.projects": "帮扶项目管理",
    "nav.funds": "资金管理",
    "nav.schools": "帮扶学校管理",
    "nav.policy": "政策法规",
    "nav.reports": "报表中心",
    "nav.system": "系统管理",
    "nav.settings": "系统设置",
    "action.save": "保存",
    "action.cancel": "取消",
    "action.delete": "删除",
    "action.edit": "编辑",
    "action.add": "新增",
    "action.search": "搜索",
    "action.export": "导出",
    "action.import": "导入",
    "action.submit": "提交",
    "action.approve": "审批",
    "action.reject": "驳回",
    "action.refresh": "刷新",
    "action.close": "关闭",
    "action.confirm": "确认",
    "status.success": "操作成功",
    "status.failure": "操作失败",
    "status.loading": "加载中...",
    "status.pending": "待处理",
    "status.approved": "已通过",
    "status.rejected": "已驳回",
    "message.confirm_delete": "确认要删除该数据吗？此操作不可撤销。",
    "message.save_success": "数据保存成功",
    "message.delete_success": "数据删除成功",
    "message.no_data": "暂无数据",
    "message.network_error": "网络连接异常，请检查网络设置",
    "message.unauthorized": "登录已过期，请重新登录",
    "message.forbidden": "权限不足，请联系管理员",
    "validation.required": "此项为必填项",
    "validation.max_length": "输入内容超出最大长度限制",
    "validation.invalid_format": "输入格式不正确",
    "label.username": "用户名",
    "label.password": "密码",
    "label.organization": "所属单位",
    "label.role": "角色",
    "label.created_at": "创建时间",
    "label.updated_at": "更新时间",
    "label.status": "状态",
    "label.remark": "备注",
}

# 中文（繁体）翻译资源
_ZH_TW_TRANSLATIONS: Dict[str, str] = {
    "app.title": "軍隊鄉村振興管理系統",
    "app.subtitle": "助力鄉村振興戰略實施",
    "nav.dashboard": "數據看板",
    "nav.villages": "幫扶村管理",
    "nav.projects": "幫扶項目管理",
    "nav.funds": "資金管理",
    "nav.schools": "幫扶學校管理",
    "nav.policy": "政策法規",
    "nav.reports": "報表中心",
    "nav.system": "系統管理",
    "nav.settings": "系統設置",
    "action.save": "儲存",
    "action.cancel": "取消",
    "action.delete": "刪除",
    "action.edit": "編輯",
    "action.add": "新增",
    "action.search": "搜尋",
    "action.export": "匯出",
    "action.import": "匯入",
    "action.submit": "提交",
    "action.approve": "審批",
    "action.reject": "駁回",
    "action.refresh": "重新整理",
    "action.close": "關閉",
    "action.confirm": "確認",
    "status.success": "操作成功",
    "status.failure": "操作失敗",
    "status.loading": "載入中...",
    "status.pending": "待處理",
    "status.approved": "已通過",
    "status.rejected": "已駁回",
    "message.confirm_delete": "確認要刪除該數據嗎？此操作不可撤銷。",
    "message.save_success": "數據儲存成功",
    "message.delete_success": "數據刪除成功",
    "message.no_data": "暫無數據",
    "message.network_error": "網路連線異常，請檢查網路設定",
    "message.unauthorized": "登入已過期，請重新登入",
    "message.forbidden": "權限不足，請聯繫管理員",
}

# 英文翻译资源
_EN_TRANSLATIONS: Dict[str, str] = {
    "app.title": "Assistance Management Information System",
    "app.subtitle": "Supporting Rural Revitalization Strategy",
    "nav.dashboard": "Dashboard",
    "nav.villages": "Village Management",
    "nav.projects": "Project Management",
    "nav.funds": "Fund Management",
    "nav.schools": "School Management",
    "nav.policy": "Policies",
    "nav.reports": "Reports",
    "nav.system": "System",
    "nav.settings": "Settings",
    "action.save": "Save",
    "action.cancel": "Cancel",
    "action.delete": "Delete",
    "action.edit": "Edit",
    "action.add": "Add",
    "action.search": "Search",
    "action.export": "Export",
    "action.import": "Import",
    "action.submit": "Submit",
    "action.approve": "Approve",
    "action.reject": "Reject",
    "action.refresh": "Refresh",
    "action.close": "Close",
    "action.confirm": "Confirm",
    "status.success": "Operation Successful",
    "status.failure": "Operation Failed",
    "status.loading": "Loading...",
    "status.pending": "Pending",
    "status.approved": "Approved",
    "status.rejected": "Rejected",
    "message.confirm_delete": "Are you sure you want to delete this data? This action cannot be undone.",
    "message.save_success": "Data saved successfully",
    "message.delete_success": "Data deleted successfully",
    "message.no_data": "No data available",
    "message.network_error": "Network error, please check your connection",
    "message.unauthorized": "Session expired, please log in again",
    "message.forbidden": "Insufficient permissions, please contact administrator",
}


# ==================== Pydantic 模型 ====================

class TranslationResource(BaseModel):
    """翻译资源"""
    language: str = Field(..., description="语言代码: zh-CN/zh-TW/en")
    translations: Dict[str, str] = Field(..., description="翻译键值对")


# ==================== API 端点 ====================

@router.get("/languages", summary="获取支持的语言列表")
async def get_supported_languages():
    """获取系统支持的语言列表"""
    return {
        "success": True,
        "data": [
            {"code": "zh-CN", "name": "中文（简体）", "flag": "CN", "default": True},
            {"code": "zh-TW", "name": "中文（繁體）", "flag": "TW", "default": False},
            {"code": "en", "name": "English", "flag": "US", "default": False},
        ],
    }


@router.get("/translations/{language}", summary="获取指定语言的翻译资源")
async def get_translations(
    language: str = "zh-CN",
    namespace: Optional[str] = Query(None, description="按命名空间筛选（如 nav、action、status）"),
):
    """获取指定语言的完整或命名空间内的翻译资源"""
    translations_map = {
        "zh-CN": _ZH_CN_TRANSLATIONS,
        "zh-TW": _ZH_TW_TRANSLATIONS,
        "en": _EN_TRANSLATIONS,
    }

    if language not in translations_map:
        raise HTTPException(status_code=400, detail=f"不支持的语言: {language}")

    translations = translations_map[language]

    if namespace:
        prefix = namespace + "."
        translations = {k: v for k, v in translations.items() if k.startswith(prefix)}

    return {
        "success": True,
        "data": {
            "language": language,
            "translations": translations,
            "total_keys": len(translations),
        },
    }


@router.get("/translate", summary="翻译单个键值")
async def translate_key(
    key: str = Query(..., description="翻译键"),
    language: str = Query("zh-CN", description="目标语言"),
):
    """获取指定键在目标语言下的翻译文本"""
    translations_map = {
        "zh-CN": _ZH_CN_TRANSLATIONS,
        "zh-TW": _ZH_TW_TRANSLATIONS,
        "en": _EN_TRANSLATIONS,
    }

    if language not in translations_map:
        raise HTTPException(status_code=400, detail=f"不支持的语言: {language}")

    translations = translations_map[language]
    value = translations.get(key)

    if value is None:
        # 回退到简体中文
        value = _ZH_CN_TRANSLATIONS.get(key, key)

    return {
        "success": True,
        "data": {
            "key": key,
            "language": language,
            "value": value,
            "fallback": value == key,
        },
    }


@router.get("/missing-keys", summary="检查缺失的翻译键")
async def get_missing_keys(
    source_lang: str = Query("zh-CN", description="源语言"),
    target_lang: str = Query("en", description="目标语言"),
    current_user=Depends(get_current_user),
):
    """比较两种语言的翻译资源，找出目标语言中缺失的键"""
    translations_map = {
        "zh-CN": _ZH_CN_TRANSLATIONS,
        "zh-TW": _ZH_TW_TRANSLATIONS,
        "en": _EN_TRANSLATIONS,
    }

    if source_lang not in translations_map or target_lang not in translations_map:
        raise HTTPException(status_code=400, detail="不支持的语言")

    source = translations_map[source_lang]
    target = translations_map[target_lang]

    missing_keys = [k for k in source if k not in target]
    extra_keys = [k for k in target if k not in source]

    return {
        "success": True,
        "data": {
            "source_language": source_lang,
            "target_language": target_lang,
            "source_count": len(source),
            "target_count": len(target),
            "missing_keys": missing_keys,
            "missing_count": len(missing_keys),
            "extra_keys": extra_keys,
            "completion_rate": round((len(target) - len(missing_keys)) / len(source) * 100, 1) if source else 100,
        },
    }


@router.get("/current", summary="获取当前用户语言偏好")
async def get_current_language(current_user=Depends(get_current_user)):
    """获取当前用户的语言设置"""
    # 实际可从用户配置中读取
    return {
        "success": True,
        "data": {
            "language": "zh-CN",
            "name": "中文（简体）",
        },
    }
