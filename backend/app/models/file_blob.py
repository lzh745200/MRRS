"""文件内容 blob 去重表（内容寻址存储，P2-2）。

设计目标
--------
系统内多套上传实现各自落盘，同一份内容被重复上传时会生成多份物理副本，
既浪费磁盘也让"哪些文件仍被引用"变得不可判定。本表以内容 SHA-256 作为
主键，把「物理文件」与「引用它的业务记录」解耦：

- 主键 ``sha256``：内容寻址。相同内容 → 同一行 → 同一物理文件；
- ``path``：物理文件的绝对路径（首次落盘位置）；
- ``size``：文件字节数（复用下载/统计，避免重复 stat）；
- ``ref_count``：引用计数。上传命中即 +1，删除命中即 -1，归零才删物理文件
  与记录（见 ``app.utils.upload_helper.delete_attachment_file``）；
- ``created_at``：首次落盘时间。

与既有模型约定保持一致：沿用 ``Base`` 声明式基类与显式 ``Column`` 定义
（本表以内容摘要为主键，不使用自增 ``id``，故不继承 ``BaseModel``）。

引用计数一致性
--------------
只有「上传登记 + 删除递减」两条链路都完备的业务（当前为经费附件
``funds.py``）才传 ``db`` 启用登记；未登记的历史文件在删除时走原有
「直接删物理文件」路径，行为与改造前完全一致。
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.models.base import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间（timezone-aware）。"""
    return datetime.now(timezone.utc)


class FileBlob(Base):
    """文件内容去重表。

    以内容 SHA-256 为主键，实现「同内容复用物理存储 + 引用计数回收」。
    """

    __tablename__ = "file_blobs"

    sha256 = Column(String(64), primary_key=True, comment="内容 SHA-256 摘要（内容寻址主键）")
    path = Column(String(500), nullable=False, comment="物理文件绝对路径")
    size = Column(Integer, nullable=False, default=0, server_default="0", comment="文件大小（字节）")
    ref_count = Column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="引用计数（归零才删除物理文件）",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=_utcnow,
        server_default=func.now(),
        nullable=False,
        comment="首次落盘时间",
    )

    def __repr__(self) -> str:  # pragma: no cover - 调试表示
        return f"<FileBlob(sha256={self.sha256[:12]}..., ref_count={self.ref_count})>"
