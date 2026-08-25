"""生成硬编码颜色存量报告（P4 批次任务队列工件）。

用法: backend/.venv/Scripts/python scripts/gen_color_report.py
输出: frontend/docs/design/hardcoded-colors-report.md
"""

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "scripts" / "hardcoded_styles_baseline.json"
OUT = ROOT / "frontend" / "docs" / "design" / "hardcoded-colors-report.md"

b = json.loads(BASELINE.read_text(encoding="utf-8"))
total = sum(len(v) for v in b.values())
colors: collections.Counter = collections.Counter()
for v in b.values():
    colors.update(v)
files = sorted(b.items(), key=lambda kv: -len(kv[1]))

mapping = {
    "#1b4332": "var(--military-dark) / $military-dark（深军绿标题/背景）",
    "#303133": "var(--color-text-primary)（EP 主文字）",
    "#fff": "var(--color-bg-card)",
    "#666": "var(--color-text-secondary)",
    "#606266": "var(--color-text-regular)",
    "#f5f7fa": "var(--color-bg-hover)",
    "#d4af37": "$badge-gold（金色徽章语义保留，可命名 token 化）",
    "#ffffff": "var(--color-bg-card)",
    "#e4e7ed": "var(--color-border-light)",
    "rgba(0, 0, 0, 0.06)": "border-light 或阴影 token 分解",
    "#2d6a4f": "var(--color-primary)",
    "#40916c": "var(--color-primary-light-1)",
    "#f0f0f0": "var(--color-bg-hover)",
    "#ebeef5": "var(--color-border-light)",
    "#003366": "dashboard-theme 深蓝 → 建议新 token --color-navy",
}

top_colors = sum(n for _, n in colors.most_common(15))

lines: list[str] = []
lines.append("# 硬编码颜色存量报告（P4 批次任务队列）")
lines.append("")
lines.append(
    f"> 生成：`check_hardcoded_styles.py --update-baseline` ｜ 存量 **{total} 处 / {len(b)} 文件**"
    "（基线已冻结，只减不增）"
)
lines.append(
    "> 消化方式：按映射表替换为 `var(--token)` → 跑 vitest+vue-tsc → `--update-baseline` 收紧基线。"
)
lines.append("")
lines.append("## 颜色频次 Top15（映射表依据）")
lines.append("")
lines.append(f"> Top15 字面量合计 {top_colors}/{total} 处（约 {round(top_colors * 100 / total)}%），映射直换即可消化大半。")
lines.append("")
lines.append("| 次数 | 字面量 | 建议映射 |")
lines.append("|---|---|---|")
for c, n in colors.most_common(15):
    lines.append(f"| {n} | `{c}` | {mapping.get(c, '人工审')} |")
lines.append("")
lines.append("## 文件存量 Top20（批次顺序）")
lines.append("")
lines.append("| 存量 | 文件 |")
lines.append("|---|---|")
for fp, v in files[:20]:
    lines.append(f"| {len(v)} | `{fp}` |")
lines.append("")
lines.append("## 批次建议")
lines.append("")
lines.append("- **B1（映射直换）**：上表 Top15 字面量机械替换，风险最低、覆盖最大")
lines.append("- **B2（文件攻坚）**：DefaultLayoutSafe/AdminDashboard/LoginEnhanced 三文件占 172 处，逐文件人工过")
lines.append("- **B3（长尾抽检）**：剩余按目录批量 + 20% 抽检截图对比")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"written {OUT} ({total} violations / {len(b)} files)")
