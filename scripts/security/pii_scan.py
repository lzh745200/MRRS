# -*- coding: utf-8 -*-
"""
T050：军规合规终检 —— PII 三通道扫描器

扫描范围：
  1) API 响应通道：后端响应模型/路由是否直接外泄敏感字段而未脱敏
  2) Excel 导出通道：导出逻辑是否包含敏感字段且未脱敏
  3) 日志通道：是否明文打印密码/身份证/银行卡等

判定：
  - 敏感字段出现在「响应模型 to_dict / response 构造 / 路由返回」且同文件无 desensitize/encrypt 调用 => 高危
  - 日志通道出现 password/id_card/bank_card 明文打印 => 高危
  - Excel 导出含敏感字段且同导出函数未调用 desensitize => 中危

输出零高危即视为通过发布门禁。
"""
import io
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend" / "app"
FRONTEND = ROOT / "frontend" / "src"

# 敏感字段命名（中文+英文）
SENSITIVE = [
    r"id_card", r"idcard", r"id_number", r"identity",
    r"bank_card", r"bankcard", r"bank_account",
    r"password", r"passwd", r"secret", r"token",
    r"phone", r"mobile", r"tel",
    r"身份证", r"银行卡", r"密码",
]
SENSITIVE_RE = re.compile(r"(?i)(" + "|".join(SENSITIVE) + r")")

# 脱敏/加密标记
SAFE_MARK = re.compile(r"(?i)(desensitize|encrypt|mask|脱敏|加密|scramble)")

# 日志通道危险模式：明文打印敏感字段
LOG_DANGER_RE = re.compile(
    r"(?i)(logger|logging|print|console\.log|printf?)\b.*\b("
    + "|".join([r"password", r"passwd", r"id_card", r"bank_card", r"secret", r"token"])
    + r")\b"
)

HIGH = []
MED = []


def scan_file(path: Path, rel: str):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return
    lines = text.splitlines()

    # 日志通道高危
    for i, ln in enumerate(lines, 1):
        if LOG_DANGER_RE.search(ln):
            # 排除本身就在脱敏/加密函数内的打印
            if not SAFE_MARK.search(ln):
                HIGH.append(f"[LOG] {rel}:{i} 明文打印敏感字段 -> {ln.strip()[:120]}")

    # 敏感字段出现位置
    hits = [i for i, ln in enumerate(lines, 1) if SENSITIVE_RE.search(ln)]
    if not hits:
        return

    # 同文件是否出现脱敏/加密标记
    has_safe = bool(SAFE_MARK.search(text))

    # 判定是否为响应模型 / 导出 / 路由返回上下文
    is_response = bool(re.search(r"(?i)(to_dict|response|success_response|BaseModel|@router\.)", text))
    is_export = bool(re.search(r"(?i)(export|to_excel|workbook|csv|openpyxl|xlsxwriter)", text))

    for i in hits:
        ln = lines[i - 1]
        # 字段定义（模型列/属性）本身不算高危，只要同文件有脱敏实践
        if has_safe:
            continue
        if is_response:
            HIGH.append(f"[API] {rel}:{i} 响应通道暴露敏感字段且无脱敏 -> {ln.strip()[:120]}")
        elif is_export:
            MED.append(f"[EXPORT] {rel}:{i} 导出通道含敏感字段未脱敏 -> {ln.strip()[:120]}")


def walk(root: Path, exts):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in exts:
            yield p


def main() -> int:
    for p in walk(BACKEND, {".py"}):
        scan_file(p, str(p.relative_to(ROOT)))
    for p in walk(FRONTEND, {".ts", ".vue"}):
        scan_file(p, str(p.relative_to(ROOT)))

    print("=" * 60)
    print("PII 三通道扫描结果")
    print("=" * 60)
    print(f"高危: {len(HIGH)}   中危: {len(MED)}")
    for h in HIGH:
        print("  HIGH " + h)
    for m in MED:
        print("  MED  " + m)
    print("=" * 60)
    if HIGH:
        print("RESULT: FAIL (存在高危项，禁止带病发布)")
        return 1
    print("RESULT: PASS (零高危，满足发布门禁)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
