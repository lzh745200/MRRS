"""
舆情监控数据模型

SentimentNews: 采集的舆情新闻（含情感分析结果）

说明：该模型此前缺失（app/api/v1/sentiment.py 与
app/services/sentiment/crawler_service.py 均引用
app.models.sentiment.SentimentNews 但文件不存在），
2026-07-17 按两处实际使用字段补齐。
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Float, String, Text
from sqlalchemy.sql import func

from app.models.base import BaseModel, UtcDateTime


class SentimentNews(BaseModel):
    """舆情新闻记录"""

    __tablename__ = "sentiment_news"

    title = Column(String(500), nullable=False, comment="新闻标题")
    source = Column(String(200), nullable=True, comment="来源（RSS 源/站点名）")
    url = Column(String(1000), nullable=True, comment="原文链接")
    content = Column(Text, nullable=True, comment="正文内容")
    author = Column(String(100), nullable=True, comment="作者")
    published_at = Column(UtcDateTime(), nullable=True, index=True, comment="发布时间")
    # 迁移 006 建的是 NOT NULL 且无 server_default —— 而全仓无任何写入点填该列，
    # 迁移建的库插入必失败，create_all 建的库却可空，行为分裂（深审 LIVE）。
    # 统一为「ORM 侧必有值 + 物理列放宽」，两侧语义一致。
    collected_at = Column(
        UtcDateTime(),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=True,
        comment="采集时间",
    )

    # 关键词（crawler 以英文逗号拼接存储；分析后重写为逗号拼接的热词）
    keywords = Column(String(500), nullable=True, default="", comment="关键词（逗号分隔）")

    # 情感分析结果
    sentiment_score = Column(Float, nullable=False, default=0.0, comment="情感分数 -1.0~1.0")
    sentiment_label = Column(
        String(20), nullable=False, default="pending",
        comment="情感分类 positive/negative/neutral/pending",
    )
    processed = Column(Boolean, nullable=False, default=False, index=True, comment="是否已完成情感分析")

    # 预警标记（负面且低于阈值时置 True）
    is_alert = Column(Boolean, nullable=False, default=False, index=True, comment="是否舆情预警")

    def __repr__(self):
        return f"<SentimentNews(id={self.id}, title={self.title!r}, label={self.sentiment_label})>"
