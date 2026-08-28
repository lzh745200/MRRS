"""全仓 mojibake（GBK↔UTF-8 双重编码）损坏扫描。

原理：正常简体中文 UTF-8 文本极少出现这些高频 GBK 双编特征字
（锛 鐨 鍏 鎵 鏈 銆 娈 涓 绠 應 纭 鍚 鐢 劧 鑾 灏 瀹 璇 釜 浠 偣 浗 佸 绯 缂 杩 椤 埘）。
命中文件再用 utf-8 strict 重读并人工复核特征行。
排除 node_modules/dist/.git 等生成目录与 lock 文件。
"""
import os
import sys

SUSPECT = set('锛鐨鍏鎵鏈銆娈涓绠應纭鍚鐢劧鑾灏瀹璇釜浠偣浗佸绯缂杩椤埘澶囦唤鏈哄埗缂哄皯杩愯琛屾椂搴撱')

SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv',
             'venv', '.pytest_cache', '.mypy_cache', 'coverage', '.zcode',
             'backend/dist', 'frontend/dist', 'resources/frontend', '.ruff_cache'}
SKIP_EXT = {'.png', '.jpg', '.ico', '.exe', '.zip', '.gz', '.deb', '.woff',
            '.woff2', '.ttf', '.bin', '.db', '.pyc', '.svg', '.map', '.asar'}
SKIP_FILES = {'package-lock.json', 'yarn.lock'}

hits = []
scanned = 0
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
    for f in files:
        if f in SKIP_FILES:
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in SKIP_EXT:
            continue
        p = os.path.join(root, f)
        if os.path.getsize(p) > 2_000_000:
            continue
        try:
            raw = open(p, 'rb').read()
            text = raw.decode('utf-8')  # strict：不是合法 UTF-8 本身就是坏文件
        except (UnicodeDecodeError, OSError):
            continue
        scanned += 1
        count = sum(1 for c in text if c in SUSPECT)
        if count >= 8:  # 阈值：偶发单字可能是正常词（如"锛"在日文），密集命中才是双编
            lines = text.split('\n')
            first = next(i + 1 for i, l in enumerate(lines) if sum(c in SUSPECT for c in l) >= 3)
            hits.append((p, count, first))

print(f'scanned {scanned} text files')
print(f'mojibake suspects: {len(hits)}')
for p, c, ln in sorted(hits, key=lambda x: -x[1]):
    print(f'  {p}  hits={c}  first_bad_line={ln}')
