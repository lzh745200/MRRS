"""为 GitHub Release 生成正文文件（三个发布作业共用，保证正文单源）。

## 为什么要这个脚本

Release 由 3 个作业各自上传（`build-windows.yml` 1 个 + `build-arm64.yml` 2 个），
`softprops/action-gh-release` **每次都会重写正文** —— 任何一个作业不传 body 就会把
正文清空。v1.18.1 实测正是如此：Windows 侧写了正文，随后 ARM64 两个作业把它覆盖成空，
最终 Release 正文长度为 0。

改为三个作业统一 `body_path` 指向本脚本产出的文件，内容取自仓库单源
`docs/04-部署文档/RELEASE_NOTES-<tag>.md`。

## 为什么用 Python 而不是 shell

两个工作流的 runner 不同：`build-arm64.yml` 在 ubuntu（bash），
`build-windows.yml` 在 **windows-2022（默认 PowerShell）** —— 同一段 POSIX shell
在 Windows 上会直接失败（v1.18.1 重打 tag 时踩过）。Python 两端都有，
且能可靠处理**中文目录名**（`04-部署文档`）与 UTF-8 输出。

用法：
    python scripts/prepare_release_body.py --tag v1.18.1 --out /tmp/release-body.md
"""

import argparse
import pathlib
import sys

# 发布说明所在目录（相对仓库根）
NOTES_DIR = pathlib.Path("docs") / "04-部署文档"

FALLBACK_TEMPLATE = """## {tag}

> 本版未提供 `docs/04-部署文档/RELEASE_NOTES-{tag}.md`，逐项变更见仓库根目录 `CHANGELOG.md`。

## 产物完整性校验（SHA256）

下载安装包与对应的 `SHA256SUMS-*.txt` 到同一目录后执行：

```bash
sha256sum -c SHA256SUMS-*.txt
```

所有行必须为 `OK`；出现 `FAILED` 表示文件损坏或被篡改，请勿安装。
"""


def find_notes(tag: str, repo_root: pathlib.Path) -> pathlib.Path | None:
    """按 tag 找发布说明；`v1.18.1` 与 `1.18.1` 两种写法都试。"""
    names = [tag, tag[1:] if tag.startswith("v") else f"v{tag}"]
    for name in names:
        candidate = repo_root / NOTES_DIR / f"RELEASE_NOTES-{name}.md"
        if candidate.is_file():
            return candidate
    return None


def build_body(tag: str, repo_root: pathlib.Path) -> tuple[str, pathlib.Path | None]:
    """返回 (正文, 命中的发布说明路径或 None)。"""
    notes = find_notes(tag, repo_root)
    if notes is not None:
        return notes.read_text(encoding="utf-8"), notes
    return FALLBACK_TEMPLATE.format(tag=tag), None


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 GitHub Release 正文文件")
    parser.add_argument("--tag", required=True, help="git tag，如 v1.18.1")
    parser.add_argument("--out", required=True, help="正文输出路径")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="仓库根目录（默认当前目录）",
    )
    args = parser.parse_args()

    body, notes = build_body(args.tag, pathlib.Path(args.repo_root))
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")

    if notes is None:
        print(f"::warning::未找到 RELEASE_NOTES-{args.tag}.md，已使用兜底正文", file=sys.stderr)
    else:
        print(f"发布正文来源: {notes.as_posix()}（{len(body)} 字符）")
    print(f"已写出: {out.as_posix()}（{len(body)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
