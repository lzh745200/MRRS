"""
批量导入优化器 — pandas 加速 Excel 导入

替换 openpyxl 逐行处理为 pandas 向量化操作，
配合 SQLAlchemy bulk_insert_mappings 大幅提升导入性能。

方案 #9 — 数据导入批量化
"""

import logging
from typing import Any, Dict, List, Tuple

from app.services.office_reader import read_rows

logger = logging.getLogger(__name__)

# 单次批量插入的批次大小
BATCH_SIZE = 500


def read_excel_raw(file_content: bytes) -> List[List[Any]]:
    """pandas 快速读取全部原始行（header=None，不做任何表头假设）。

    供 ExcelImporterService.parse_excel 使用：官方模板的表头不在第 1 行
    （前 5 行为装饰标题区），表头探测与列名映射由调用方完成。

    Returns:
        行列表，每行为单元格值列表（空值为 None，与 openpyxl values_only 一致）
    """
    # 统一走 office_reader：按容器魔数选择 openpyxl(.xlsx/.et-OOXML) 或
    # xlrd(.xls/.et-OLE2)，不再固定 engine="openpyxl"（那会让 .xls 必然失败）。
    return read_rows(file_content)


def _read_excel_fallback(file_content: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """表头+数据行回退读取（pandas 不可用时；.xlsx/.xls/WPS .et 均支持）"""
    raw = read_rows(file_content)
    if not raw:
        return [], []
    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(raw[0])]
    rows = []
    for row in raw[1:]:
        if all(v is None for v in row):
            continue
        rows.append({headers[i]: (str(v) if v is not None else "") for i, v in enumerate(row) if i < len(headers)})
    return rows, headers
