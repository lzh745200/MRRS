#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PPTX 文字溢出体检器（stdlib only）

思路：解析每个文本框的几何尺寸（EMU）、段落/run 的字号、自动缩放下限与行距，
再用 CJK 感知的宽度模型估算换行后的实际文本高度，与可用高度对比，输出溢出清单。

宽度模型（保守，贴近微软雅黑）：
  全角/中日韩字符、全角标点 : 1.00 em
  ASCII 大写字面           : 0.60 em
  小写/数字                : 0.52 em
  空格                     : 0.28 em
  西文标点                 : 0.32 em
行高模型：fontSize * 1.30（单倍行距的安全估计），段落间距按 spcAft/spcBef 叠加。
"""
import sys
import zipfile
import re
import xml.etree.ElementTree as ET

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
EMU_PER_PT = 12700
DEFAULT_SZ = 18.0  # 未显式指定字号时的兜底（pt）
LINE_H_FACTOR = 1.40   # 微软雅黑单倍行距实测约 1.34~1.42em，取保守值
BOLD_FACTOR = 1.05     # 粗体字宽加成
SAFE_MARGIN = 0.92     # 要求 文本需求高度 <= 可用高度 * SAFE_MARGIN（留 8% 余量）


def char_width(ch: str) -> float:
    o = ord(ch)
    if o < 0x20:
        return 0.0
    if ch == " ":
        return 0.28
    if o < 0x2E:
        return 0.32
    if 0x30 <= o <= 0x39:  # digits
        return 0.52
    if 0x41 <= o <= 0x5A:  # A-Z
        return 0.60
    if 0x61 <= o <= 0x7A:  # a-z
        return 0.52
    if o < 0x2000:  # other latin/punct
        return 0.400
    # CJK / 全角
    if 0x2E80 <= o <= 0x9FFF or 0xF900 <= o <= 0xFAFF or 0xFF00 <= o <= 0xFFEF:
        return 1.00
    if 0x2000 <= o <= 0x206F:
        return 0.50
    return 1.00


def text_width_em(s: str) -> float:
    return sum(char_width(c) for c in s)


def _shape_geom(sp):
    """返回 (name, x, y, w, h, kind) 单位 pt；kind: 'card' | 'text' | 'other'"""
    nv = sp.find(".//p:cNvPr", NS)
    name = nv.get("name") if nv is not None else "?"
    xfrm = sp.find(".//a:xfrm", NS)
    if xfrm is None:
        return None
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None
    x = int(off.get("x", 0)) / EMU_PER_PT
    y = int(off.get("y", 0)) / EMU_PER_PT
    w = int(ext.get("cx", 0)) / EMU_PER_PT
    h = int(ext.get("cy", 0)) / EMU_PER_PT
    geom = sp.find(".//a:prstGeom", NS)
    prst = geom.get("prst") if geom is not None else None
    has_fill = sp.find(".//p:spPr/a:solidFill", NS) is not None
    tx = sp.find(".//p:txBody", NS)
    has_text = False
    if tx is not None:
        for r in tx.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}t"):
            if (r.text or "").strip():
                has_text = True
                break
    if prst in ("roundRect", "rect") and has_fill and not has_text:
        kind = "card"
    elif has_text:
        kind = "text"
    else:
        kind = "other"
    return (name, x, y, w, h, kind)


def analyze_slide(xml_bytes: bytes):
    """返回 (texts, cards)；texts 为溢出记录列表"""
    root = ET.fromstring(xml_bytes)
    shapes = []
    for sp in root.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sp"):
        g = _shape_geom(sp)
        if g:
            shapes.append((g, sp))
    cards = [(g[1], g[2], g[3], g[4]) for g, _ in shapes if g[5] == "card"]
    out = []
    for g, sp in shapes:
        if g[5] != "text":
            continue
        name, bx, by, bw, bh = g[0], g[1], g[2], g[3], g[4]
        tx = sp.find(".//p:txBody", NS)
        body = tx.find("a:bodyPr", NS)
        l_ins = r_ins = t_ins = b_ins = 0.0
        if body is not None:
            l_ins = int(body.get("lIns", 91440)) / EMU_PER_PT
            r_ins = int(body.get("rIns", 91440)) / EMU_PER_PT
            t_ins = int(body.get("tIns", 45720)) / EMU_PER_PT
            b_ins = int(body.get("bIns", 45720)) / EMU_PER_PT
        avail_w = bw - l_ins - r_ins
        if avail_w <= 1:
            continue
        req_h = 0.0
        sample_parts = []
        for para in tx.findall("a:p", NS):
            pPr = para.find("a:pPr", NS)
            indent = 0.0
            spc_aft = spc_bef = 0
            if pPr is not None:
                indent = int(pPr.get("marL", 0)) / EMU_PER_PT
                spc_aft = int(pPr.get("spcAft", "0") or 0)
                spc_bef = int(pPr.get("spcBef", "0") or 0)
            segs = []
            for r in para.findall("a:r", NS):
                t = r.find("a:t", NS)
                txt = (t.text or "") if t is not None else ""
                rPr = r.find("a:rPr", NS)
                sz = DEFAULT_SZ
                bold = False
                if rPr is not None:
                    if rPr.get("sz"):
                        sz = int(rPr.get("sz")) / 100.0
                    bold = rPr.get("b") == "1"
                segs.append((txt, sz * (BOLD_FACTOR if bold else 1.0)))
            if not segs:
                continue
            max_sz = max(s for _, s in segs) or DEFAULT_SZ
            line_h = max_sz * LINE_H_FACTOR
            usable = max(avail_w - indent, 1.0)
            lines = 1
            acc = 0.0
            for t, s in segs:
                for ch in t:
                    w_em = char_width(ch) * s
                    if acc + w_em > usable:
                        lines += 1
                        acc = 0.0
                    acc += w_em
            req_h += lines * line_h + (spc_bef + spc_aft) / 100.0
            sample_parts.append("".join(t for t, _ in segs)[:36])
        if req_h <= 0:
            continue
        # 自身文本框容量
        own_avail = bh - t_ins - b_ins
        # 所在卡片容量：取包含该文本框左上角、面积最小的卡片
        container = None
        for cx, cy, cw, chh in cards:
            if (cx - 3 <= bx <= cx + cw + 3) and (cy - 3 <= by <= cy + chh + 3):
                if cw > bw - 3 and chh > 0:
                    if container is None or cw * chh < container[2] * container[3]:
                        container = (cx, cy, cw, chh)
        if container:
            _, _, _, chh = container
            card_avail = (container[1] + chh) - by - 8.0  # 卡片底边 - 文本框顶 - 8pt 内边距
            avail_h = max(min(own_avail, card_avail), 1.0)
            ref = "卡片"
        else:
            avail_h = max(own_avail, 1.0)
            ref = "文本框"
        # 页面安全区：底边 7.5in - 0.35in 内边距 = 7.15in = 514.8pt
        # 页脚/页码区（y >= 495pt）本就贴着底边，不参与页底规则，避免噪声
        if by < 495:
            page_avail = 514.8 - by
            if page_avail < avail_h:
                avail_h = max(page_avail, 1.0)
                ref = ref + "+页底"
        out.append((name, bx, by, bw, bh, req_h, avail_h * SAFE_MARGIN, ref, " | ".join(sample_parts)[:70]))
    return out


def parse_slide(xml_bytes: bytes):
    return analyze_slide(xml_bytes)



def main(path: str, threshold: float = 1.0):
    z = zipfile.ZipFile(path)
    names = [n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)]
    names.sort(key=lambda n: int(re.search(r"(\d+)", n.split("/")[-1]).group(1)))
    bad_total = 0
    print(f"文件: {path}  共 {len(names)} 页  (阈值 溢出比 >= {threshold})")
    for idx, n in enumerate(names, 1):
        items = analyze_slide(z.read(n))
        bad = [i for i in items if (i[5] / i[6]) >= threshold]
        if not bad:
            continue
        bad.sort(key=lambda i: -(i[5] / i[6]))
        print(f"\n=== 第 {idx} 页：{len(bad)} 处溢出 ===")
        for name, bx, by, bw, bh, req, avail, ref, sample in bad:
            print(f"  [{req / avail:4.2f}x] 超出{ref} {name} 位置({bx:.0f},{by:.0f}) {bw:.0f}x{bh:.0f}pt  需{req:.1f}/可用{avail:.1f}pt")
            print(f"          文本: {sample}")
        bad_total += len(bad)
    print(f"\n>>> 合计溢出文本框: {bad_total}")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "docs/帮扶管理信息系统介绍.pptx"
    th = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    if len(sys.argv) > 3:
        LINE_H_FACTOR = float(sys.argv[3])
    print(f"[度量] 行高系数={LINE_H_FACTOR} 粗体加成={BOLD_FACTOR} 安全余量={SAFE_MARGIN}")
    main(p, th)
