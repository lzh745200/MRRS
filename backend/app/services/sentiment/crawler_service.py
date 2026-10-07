"""
情感爬虫服务

提供网络情感数据采集功能。

⚠️ 离线部署注意：本模块默认禁用网络爬虫功能（ENABLE_CRAWLER=false）。
仅用于联网环境的舆情监控扩展，离线单机部署不需要此功能。
"""

import os
from dataclasses import dataclass, field
from datetime import timezone, datetime
from typing import List, Optional, Dict, Any
from app.core.transaction import safe_commit

# 离线单机版默认禁用爬虫；联网部署时设置环境变量 ENABLE_CRAWLER=true 启用
_CRAWLER_ENABLED = os.getenv("ENABLE_CRAWLER", "").strip().lower() in ("true", "1", "yes")

if not _CRAWLER_ENABLED:  # pragma: no cover - 导入期环境分支：ENABLE_CRAWLER 导入时求值，测试进程禁止 reload 服务模块，启用侧仅联网部署执行
    import logging
    _log = logging.getLogger(__name__)
    _log.info("爬虫服务已禁用（离线模式）。设置 ENABLE_CRAWLER=true 以启用。")


@dataclass
class SentimentData:
    """情感数据模型"""

    id: str
    source: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any]


@dataclass
class NewsItem:
    """新闻条目"""

    id: Optional[int] = None
    title: str = ""
    source: str = ""
    url: str = ""
    content: str = ""
    published_at: Optional[datetime] = None
    keywords: List[str] = field(default_factory=list)
    sentiment_score: float = 0.0
    sentiment_label: str = ""
    is_alert: bool = False


class SentimentCrawlerService:
    """
    情感爬虫服务

    负责从各种来源采集情感数据
    """

    def __init__(self):
        self.sources = []
        self.crawled_data = []

    def crawl_news(self, keywords: List[str], limit: int = 100) -> List[SentimentData]:
        """
        爬取新闻数据

        Args:
            keywords: 搜索关键词列表
            limit: 最大返回数量

        Returns:
            List[SentimentData]: 采集到的情感数据列表
        """
        # 模拟爬取新闻数据
        return []

    def crawl_social_media(self, keywords: List[str], platforms: List[str], limit: int = 100) -> List[SentimentData]:
        """
        爬取社交媒体数据

        Args:
            keywords: 搜索关键词列表
            platforms: 目标平台列表
            limit: 最大返回数量

        Returns:
            List[SentimentData]: 采集到的情感数据列表
        """
        # 模拟爬取社交媒体数据
        return []

    def parse_content(self, raw_content: str, source_type: str) -> Dict[str, Any]:
        """
        解析原始内容

        Args:
            raw_content: 原始内容文本
            source_type: 内容来源类型

        Returns:
            Dict[str, Any]: 解析后的内容结构
        """
        return {
            "text": raw_content,
            "source_type": source_type,
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }


class CrawlerService:
    """
    爬虫服务（API兼容包装类）

    为 sentiment API 提供兼容的静态方法接口
    """

    _instance: Optional[SentimentCrawlerService] = None

    @classmethod
    def _get_instance(cls) -> SentimentCrawlerService:
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = SentimentCrawlerService()
        return cls._instance

    @staticmethod
    def fetch_rss_feeds(db, keywords: List[str]) -> List[NewsItem]:
        """
        从RSS源获取新闻

        Args:
            db: 数据库会话
            keywords: 搜索关键词列表

        Returns:
            List[NewsItem]: 获取到的新闻列表
        """
        # 离线模式：不执行网络爬虫
        if not _CRAWLER_ENABLED:
            return []

        # 模拟RSS抓取（仅在 ENABLE_CRAWLER=true 时执行）
        import logging
        logging.getLogger(__name__).warning("爬虫服务使用模拟数据，生产环境请配置真实RSS源")
        news_list = []
        for i, keyword in enumerate(keywords[:5]):  # 限制关键词数量
            news_list.append(
                NewsItem(
                    id=None,
                    title=f"关于{keyword}的新闻",
                    source="RSS Feed",
                    url="",  # 生产环境需配置真实URL
                    content=f"这是关于{keyword}的新闻内容",
                    published_at=datetime.now(timezone.utc),
                    keywords=[keyword],
                )
            )
        return news_list

    @staticmethod
    def save_news(db, news_list: List[NewsItem]) -> int:
        """
        保存新闻到数据库

        Args:
            db: 数据库会话
            news_list: 新闻列表

        Returns:
            int: 保存成功的新闻数量
        """
        try:
            from app.models.sentiment import SentimentNews

            saved_count = 0
            for news in news_list:
                db_news = SentimentNews(
                    title=news.title,
                    source=news.source,
                    url=news.url,
                    content=news.content,
                    published_at=news.published_at or datetime.now(timezone.utc),
                    keywords=",".join(news.keywords) if news.keywords else "",
                    sentiment_score=0.0,
                    sentiment_label="pending",
                    is_alert=False,
                )
                db.add(db_news)
                saved_count += 1

            safe_commit(db)
            return saved_count
        except Exception as e:
            db.rollback()
            raise e
