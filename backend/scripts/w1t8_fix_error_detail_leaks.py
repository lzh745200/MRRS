"""W1-T8 批量修复：清除 api/v1 下 detail=f"...{e}/{str(e)}" 内部异常直出。

规则：
- 仅处理单行、且 f-string 中除尾部异常插值外不含其他 `{...}` 插值的行
- 形如 detail=f"<前缀>: {str(e)}" → detail="<前缀>，请稍后重试或联系管理员"
- 前缀若已以 失败/错误 结尾则直接接逗号句式
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app" / "api" / "v1"

PATTERN = re.compile(
    r'detail=f"(?P<msg>[^"{]*?)\s*[:：]\s*\{\s*(?:str\(e\)|e|repr\(e\))\s*\}"'
)

changed = []
for py in sorted(ROOT.rglob("*.py")):
    text = py.read_text(encoding="utf-8")
    original = text

    def _sub(m):
        msg = m.group("msg").strip()
        if not msg:
            return m.group(0)
        suffix = "，请稍后重试或联系管理员"
        return f'detail="{msg}{suffix}"'

    new_text = PATTERN.sub(_sub, text)
    if new_text != original:
        n = len(PATTERN.findall(original))
        py.write_text(new_text, encoding="utf-8", newline="")
        changed.append((py.relative_to(ROOT.parent.parent), n))

total = sum(n for _, n in changed)
for path, n in changed:
    print(f"{n:3d}  {path}")
print(f"--- total replaced: {total}")
