"""
舆情监控API
"""

import logging
from datetime import timezone, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user, get_db
from app.core.response import ok_list, success_response
from app.models.user import User
from app.services.sentiment.analysis_service import SentimentAnalysisService as AnalysisService
from app.services.sentiment.crawler_service import CrawlerService
from app.services.work_log_service import write_work_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sentiment", tags=["舆情监控"])


class CollectNewsRequest(BaseModel):
    """采集新闻请求"""

    keywords: List[str]


@router.post("/collect")
async def collect_news(
    request: CollectNewsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    采集新闻
    需要管理员权限
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        # 从RSS源采集
        news_list = CrawlerService.fetch_rss_feeds(db=db, keywords=request.keywords)

        # 保存到数据库
        saved_count = CrawlerService.save_news(db=db, news_list=news_list)
        write_work_log(db, "sentiment", "collect_news", 0,
                       f"新闻采集: 获取{len(news_list)}条, 新增{saved_count}条",
                       user_id=current_user.id, username=getattr(current_user, "username", ""))

        return success_response(data={"collected": len(news_list), "saved": saved_count})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to collect news")
        raise HTTPException(status_code=500, detail="新闻采集失败")


@router.post("/analyze")
async def analyze_news(
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    批量分析新闻情感
    需要管理员权限
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    try:
        processed_count = AnalysisService.analyze_news_batch(db=db, limit=limit)
        return success_response(data={"processed": processed_count})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to analyze news")
        raise HTTPException(status_code=500, detail="情感分析失败")


@router.get("/news")
async def get_news_list(
    sentiment_label: Optional[str] = None,
    is_alert: Optional[bool] = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取新闻列表"""
    from app.models.sentiment import SentimentNews

    since = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        query = db.query(SentimentNews).filter(SentimentNews.published_at >= since)

        if sentiment_label:
            query = query.filter(SentimentNews.sentiment_label == sentiment_label)

        if is_alert is not None:
            query = query.filter(SentimentNews.is_alert == is_alert)

        news_list = query.order_by(SentimentNews.published_at.desc()).limit(limit).offset(offset).all()

        return ok_list(
            items=[
                {
                    "id": news.id,
                    "title": news.title,
                    "source": news.source,
                    "url": news.url,
                    "published_at": news.published_at.isoformat() if news.published_at else None,
                    "sentiment_score": news.sentiment_score,
                    "sentiment_label": news.sentiment_label,
                    "keywords": news.keywords,
                    "is_alert": news.is_alert,
                }
                for news in news_list
            ],
            total=len(news_list),
        )
    except Exception:
        logger.exception("Failed to get news list")
        raise HTTPException(status_code=500, detail="获取新闻列表失败")


@router.get("/statistics")
async def get_sentiment_statistics(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取舆情统计"""
    from sqlalchemy import func

    from app.models.sentiment import SentimentNews

    since = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        # 统计各类情感的新闻数量
        stats = (
            db.query(SentimentNews.sentiment_label, func.count(SentimentNews.id).label("count"))
            .filter(SentimentNews.published_at >= since, SentimentNews.processed == True)  # noqa: E712
            .group_by(SentimentNews.sentiment_label)
            .all()
        )

        sentiment_counts = {label: count for label, count in stats}

        # 统计预警数量
        alert_count = (
            db.query(func.count(SentimentNews.id))
            .filter(SentimentNews.published_at >= since, SentimentNews.is_alert == True)  # noqa: E712
            .scalar()
        )

        # 获取热词
        hot_keywords = AnalysisService.generate_hot_keywords(db=db, days=days, top_k=20)

        return success_response(
            data={
                "period_days": days,
                "total_news": sum(sentiment_counts.values()),
                "positive_count": sentiment_counts.get("positive", 0),
                "negative_count": sentiment_counts.get("negative", 0),
                "neutral_count": sentiment_counts.get("neutral", 0),
                "alert_count": alert_count,
                "hot_keywords": hot_keywords,
            }
        )
    except Exception:
        logger.exception("Failed to get sentiment statistics")
        raise HTTPException(status_code=500, detail="获取舆情统计失败")


@router.get("/hot-keywords")
async def get_hot_keywords(
    days: int = Query(7, ge=1, le=90),
    top_k: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取热词列表"""
    try:
        hot_keywords = AnalysisService.generate_hot_keywords(db=db, days=days, top_k=top_k)
        return success_response(data={"period_days": days, "keywords": hot_keywords})
    except Exception:
        logger.exception("Failed to get hot keywords")
        raise HTTPException(status_code=500, detail="获取热词失败")


@router.get("/alerts")
async def get_alerts(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取预警列表"""
    from app.models.sentiment import SentimentNews

    since = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        alerts = (
            db.query(SentimentNews)
            .filter(SentimentNews.published_at >= since, SentimentNews.is_alert == True)  # noqa: E712
            .order_by(SentimentNews.published_at.desc())
            .limit(limit)
            .all()
        )

        return ok_list(
            items=[
                {
                    "id": alert.id,
                    "title": alert.title,
                    "source": alert.source,
                    "url": alert.url,
                    "published_at": alert.published_at.isoformat() if alert.published_at else None,
                    "sentiment_score": alert.sentiment_score,
                    "keywords": alert.keywords,
                }
                for alert in alerts
            ],
            total=len(alerts),
        )
    except Exception:
        logger.exception("Failed to get alerts")
        raise HTTPException(status_code=500, detail="获取预警列表失败")
