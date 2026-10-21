#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ARM64（麒麟 V10）离线 OCR 构建期冒烟（E 区 · v1.16.0）

用途：``docker/Dockerfile.kylin-standalone`` 在 pip 安装完成后执行本脚本，把
"OCR 到底能不能用"变成构建期门禁 —— 宁可构建红，也不要把"假 OCR 能力"打进
ARM64 安装包（历史教训：依赖被过滤 → 线上接口恒 503 + 手工录入，但在文档里
被写成"内置 OCR"）。

断言链（任一失败 → 非零退出 → 构建失败）：
  1. ``--require-headless`` 模式下断言**没有**装非 headless 的 ``opencv-python``
     （它会 dlopen ``libGL.so.1`` / ``libglib-2.0.so.0``，离线无图形栈的麒麟机
     import 即崩；本仓库 ARM64 一律用 ``opencv-python-headless``）。
  2. ``import cv2`` 成功并能取到版本号（headless 轮子不需要 libGL）。
  3. ``from rapidocr_onnxruntime import RapidOCR`` 成功，且 ``RapidOCR()`` 能实例化
     → onnxruntime 动态库可加载、det/rec/cls 的 ONNX 模型确实随 wheel 落地。
  4. 对 Pillow 现场合成的白底黑字 PNG 实际执行一次识别，结果非空且文本含数字
     → ``app/services/ocr_service.parse_amount`` / ``parse_date`` 的前提链路可用。

脚本不依赖仓库里的任何图片资产（现场合成 600x200 PNG），可在 ARM64 CI 构建容器、
麒麟真机、Windows 开发机（已装 requirements.txt）直接运行：

    python docker/ocr_smoke_arm64.py                    # 通用冒烟（不做 headless 硬断言）
    python docker/ocr_smoke_arm64.py --require-headless # ARM64 构建门禁（默认启用）
"""

import sys
import tempfile
from importlib import metadata
from pathlib import Path

REQUIRE_HEADLESS = "--require-headless" in sys.argv[1:]

# 合成图上的文字：纯数字 + 小数点，最贴近"凭证金额"这条真实用途
PROBE_TEXT = "12345.67"


def _installed_dist_names() -> set:
    """已安装发行包名（小写）。仅用于构建期环境断言，不用于运行时能力探测。"""
    names = set()
    for dist in metadata.distributions():
        name = (dist.metadata["Name"] or "").strip().lower()
        if name:
            names.add(name)
    return names


def check_opencv_flavor() -> None:
    """① cv2 必须是 headless 轮子（ARM64 无图形栈前提）"""
    names = _installed_dist_names()
    has_headless = "opencv-python-headless" in names
    has_full = "opencv-python" in names

    if has_full and has_headless:
        raise AssertionError(
            "同时安装了 opencv-python 与 opencv-python-headless（两包争用同一个 cv2 "
            "模块目录，行为不确定）；只允许 headless"
        )
    if REQUIRE_HEADLESS:
        if has_full:
            raise AssertionError(
                "检测到非 headless 的 opencv-python —— 它会 dlopen libGL.so.1，"
                "离线麒麟机（无图形栈）import cv2 即失败；ARM64 构建必须用 "
                "opencv-python-headless"
            )
        if not has_headless:
            raise AssertionError(
                "未安装 opencv-python-headless（ARM64 构建要求显式 headless 轮子）"
            )
        print("OK: cv2 来源 = opencv-python-headless（无 libGL 硬依赖）")
    elif has_full:
        print("WARN: 当前环境使用非 headless 的 opencv-python（本地开发可接受，"
              "ARM64 构建不允许）")
    else:
        print("OK: 未发现非 headless 的 opencv-python")


def check_cv2_import() -> None:
    """② import cv2 成功（headless 下不需要 libGL.so.1）"""
    import cv2  # noqa: PLC0415 - 冒烟脚本按需导入，便于分步定位失败点

    version = getattr(cv2, "__version__", "unknown")
    print("OK: import cv2 成功，版本 {}".format(version))
    try:
        build_info = cv2.getBuildInformation()
    except Exception:  # noqa: BLE001 - 部分构建无此 API，不影响结论
        return
    for line in build_info.splitlines():
        if line.strip().startswith("GUI:"):
            print("    cv2 {}".format(line.strip()))


def _make_probe_image(path: Path) -> None:
    """现场合成 600x200 白底黑字 PNG（不依赖仓库图片资产）"""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=80)  # Pillow >= 10.1
    except TypeError:  # Pillow < 10.1 无 size 参数
        font = ImageFont.load_default()
    draw.text((30, 50), PROBE_TEXT, fill="black", font=font)
    image.save(str(path))


def check_rapidocr_recognize() -> None:
    """③④ 引擎实例化 + 真实识别 + 数字可读"""
    from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415 - 同上，分步定位

    engine = RapidOCR()

    with tempfile.TemporaryDirectory() as tmp:
        image_path = Path(tmp) / "ocr-smoke.png"
        _make_probe_image(image_path)
        result, elapse = engine(str(image_path))

    text = "".join(str(item[1]) for item in (result or []) if len(item) >= 2)
    print("OK: RapidOCR() 实例化成功，识别耗时 {}".format(elapse))
    print("    识别文本: {!r}".format(text))
    if not result:
        raise AssertionError(
            "OCR 未识别到任何文本（模型缺失或 onnxruntime 不可用）"
        )
    if not any(ch.isdigit() for ch in text):
        raise AssertionError(
            "OCR 文本不含数字（金额解析前提失效）: {!r}".format(text)
        )
    print("OK: 识别结果含数字，ocr_service.parse_amount 前提满足")


def main() -> int:
    print("=== ARM64 离线 OCR 冒烟（require_headless={}）===".format(REQUIRE_HEADLESS))
    check_opencv_flavor()
    check_cv2_import()
    check_rapidocr_recognize()
    print("=== OK: ARM64 离线 OCR 冒烟全部通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
