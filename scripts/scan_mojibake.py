"""全仓损坏扫描：mojibake（GBK↔UTF-8 双重编码）+ NUL 空字节 + 非 UTF-8。

NUL 检测背景：backend/scripts/migrate_to_encrypted.py 曾被 sourcemap+3256 个
NUL 覆盖导致华为 CodeCheck flake8 阶段崩溃（ValueError: source code string
cannot contain null bytes），流水线整体 FAILURE；前端另有 4 个机器码伪 .scss。
本脚本三类一并拦截，--check 模式供 pre-commit/CI 使用（发现即退出码 1）。

mojibake 原理：正常简体中文 UTF-8 文本极少出现这些高频 GBK 双编特征字。
排除 node_modules/dist/.git 等生成目录与 lock 文件。
"""
import os
import sys

SUSPECT = set('锛鐨鍏鎵鏈銆娈涓绠應纭鍚鐢劧鑾灏瀹璇釜浠偣浗佸绯缂杩椤埘澶囦唤鏈哄埗缂哄皯杩愯琛屾椂搴撱')

CHECK_MODE = '--check' in sys.argv

SKIP_DIRS = {'.git', 'node_modules', 'dist', 'build', '__pycache__', '.venv',
             'venv', '.pytest_cache', '.mypy_cache', 'coverage', '.zcode',
             'backend/dist', 'frontend/dist', 'resources/frontend', '.ruff_cache',
             'logs', 'backend/logs', 'frontend/logs', 'test_scripts'}
SKIP_EXT = {'.png', '.jpg', '.ico', '.exe', '.zip', '.gz', '.deb', '.woff',
            '.woff2', '.ttf', '.bin', '.db', '.pyc', '.svg', '.map', '.asar',
            '.br', '.log', '.shm', '.wal', '.rrs', '.xlsx', '.docx', '.pptx', '.coverage'}
SKIP_FILES = {'package-lock.json', 'yarn.lock', 'scan_mojibake.py'}

# NUL 检查只针对源码文本类文件——.coverage/.log/.db-shm/.xlsx/.br 等合法
# 二进制/运行时产物天然含 NUL，不属损坏，不拦截
SRC_EXTS = {'.py', '.js', '.ts', '.tsx', '.jsx', '.vue', '.scss', '.css',
            '.html', '.md', '.sh', '.bat', '.ps1', '.nsi', '.yml', '.yaml',
            '.json', '.ini', '.toml', '.env', '.txt'}
# .bat/.ps1 允许 ANSI/GBK 编码（Windows cmd 中文批处理惯例），不做 UTF-8 强制
NON_UTF8_EXEMPT = {'.bat', '.ps1', '.nsi'}

hits = []
nul_hits = []
non_utf8 = []
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
            if b'\x00' in raw and ext in SRC_EXTS:
                nul_hits.append((p, raw.count(b'\x00')))
                if CHECK_MODE:
                    continue
            text = raw.decode('utf-8')  # strict：不是合法 UTF-8 本身就是坏文件
        except (UnicodeDecodeError, OSError):
            # 非UTF-8 检查同样限定源码文本类扩展；.coverage/.db-shm 等运行时产物豁免
            if ext in SRC_EXTS and ext not in NON_UTF8_EXEMPT:
                non_utf8.append(p)
                if CHECK_MODE:
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
if nul_hits:
    print(f'NUL-byte files: {len(nul_hits)}')
    for p, n in nul_hits:
        print(f'  {p}  nul={n}')
if non_utf8:
    print(f'non-UTF8 files: {len(non_utf8)}')
    for p in non_utf8:
        print(f'  {p}')
if CHECK_MODE and (nul_hits or non_utf8):
    print('[scan_mojibake --check] FAIL：存在 NUL/非UTF-8 损坏文件')
    sys.exit(1)
print('[scan_mojibake --check] OK' if CHECK_MODE else '')
