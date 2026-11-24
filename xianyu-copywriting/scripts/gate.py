#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""闲鱼文案体检：对照五篇黄金案例的实测分布，看一篇文案有没有跑偏。

用法：
    python scripts/gate.py <文案.md>

设计原则：**只卡硬信号，不卡结构。**
- 硬信号 = 五篇黄金案例 318 条子弹里出现 0 次的写法（方法签名串 / XML 标签 / 直角引号），
  以及偏离 2 倍以上的密度指标（单条长度、英文词数）。这些出现即说明写成了 API 大纲。
- 参考带 = 体量、模块数、子弹数。这些跟 PDF 章节厚度走，少几个模块不算错，
  只在离谱时提醒你回头看一眼。

退出码 0 = 无硬伤；1 = 有硬信号出带。
"""
import re
import sys
import pathlib
import statistics

# 硬信号：五案例里是 0，出现就是走偏
HARD_ZERO = {
    "method_calls": "方法签名串（正文里写 xxx() 调用）",
    "xml_tags": "XML 标签串（正文里罗列 <bean><property>）",
    "brackets": "「」直角引号（五案例 0 次）",
}

# 硬信号：落到区间外即返工
HARD_BAND = {
    "bullet_mean": ((27, 42), "单条平均字数"),
    "over45": ((0, 10), "超过 45 字的条数"),
    "latin_pct": ((12, 45), "英文占比 %"),
    "token_median": ((0, 3), "每条英文词数（中位）"),
    "arrows": ((0, 14), "箭头 → 数量"),
}

# 参考带：跟 PDF 厚度走，出带只提醒
REF_BAND = {
    "total": ((2200, 3900), "全文去空白字数"),
    "modules": ((5, 12), "模块数"),
    "bullets": ((38, 72), "子弹总数"),
    "per_module": ((3.0, 8.0), "每模块平均条数"),
}

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.$#/-]*")
METHOD = re.compile(r"[A-Za-z_]\w*\(")
XMLTAG = re.compile(r"<[a-zA-Z/]")


def n(s):
    return len(re.sub(r"\s", "", s))


def parse(path):
    t = pathlib.Path(path).read_text(encoding="utf-8").replace("\r", "")
    lines = t.split("\n")

    def find(prefix):
        for i, l in enumerate(lines):
            if l.strip().startswith(prefix):
                return i
        return -1

    i_guide = find("笔记的硬核精华")
    i_fit = find("适合群体")
    i_kw = find("关键词")
    i_decl = find("重要声明")
    i_deliver = find("拍下后")

    # 标题可能不在第一行（比如文件带了说明性的引用块），在前 20 行里找
    i_title = next((i for i in range(min(20, len(lines)))
                    if lines[i].strip().startswith("《")), -1)
    sub_idx = i_title + 1 if i_title >= 0 else -1

    groups, cur = [], None
    if i_guide >= 0 and i_fit > i_guide:
        for l in lines[i_guide:i_fit]:
            if re.match(r"^\s*\d+\.【", l):
                cur = []
                groups.append(cur)
            elif re.match(r"^\s*-\s", l) and cur is not None:
                cur.append(re.sub(r"^\s*-\s*", "", l.strip()))

    return {
        "lines": lines, "groups": groups,
        "has_title": i_title >= 0,
        "has_sub": bool(sub_idx > 0 and sub_idx < len(lines)
                        and lines[sub_idx].strip().startswith("｜")),
        "has_intro": i_guide > 2,
        "has_decl": i_decl >= 0,
        "has_fit": i_fit >= 0,
        "has_kw": i_kw >= 0,
        "has_deliver": i_deliver >= 0,
        "kw_count": len(re.findall(r"#\S+", lines[i_kw])) if i_kw >= 0 else 0,
        "text": t,
    }


def report(path):
    p = parse(path)
    allb = [b for g in p["groups"] for b in g]
    if not allb:
        print("✗ 没解析到模块子弹，先检查骨架是否完整")
        return False

    L = [n(b) for b in allb]
    lat = sum(len(re.findall(r"[A-Za-z]", b)) for b in allb)
    toks = sorted(len(TOKEN.findall(b)) for b in allb)
    per_mod = [len(g) for g in p["groups"]]

    m = {
        "total": n(p["text"]),
        "modules": len(p["groups"]),
        "bullets": len(allb),
        "per_module": statistics.mean(per_mod),
        "bullet_mean": statistics.mean(L),
        "over45": sum(1 for x in L if x > 45),
        "latin_pct": lat / sum(L) * 100,
        "token_median": toks[len(toks) // 2],
        "method_calls": sum(1 for b in allb if METHOD.search(b)),
        "xml_tags": sum(1 for b in allb if XMLTAG.search(b)),
        "brackets": sum(b.count("「") for b in allb),
        "arrows": sum(b.count("→") for b in allb),
    }

    print(f"文件：{pathlib.Path(path).name}")
    print(f"  骨架：", " ".join(
        f"{'✓' if ok else '✗'}{name}" for name, ok in [
            ("标题", p["has_title"]), ("副标题", p["has_sub"]), ("首段", p["has_intro"]),
            ("模块区", bool(p["groups"])), ("声明", p["has_decl"]), ("适合群体", p["has_fit"]),
            ("关键词", p["has_kw"]), ("交付行", p["has_deliver"]),
        ]), f"｜ 关键词 {p['kw_count']} 个")
    print(f"  体量：全文 {m['total']} 字 ｜ 模块 {m['modules']} ｜ 子弹 {m['bullets']} ｜ 每模块 {per_mod}")
    print(f"  手感：单条 均 {m['bullet_mean']:.1f} / 中位 {statistics.median(L):.0f} / 最长 {max(L)}"
          f" ｜ 超45字 {m['over45']} 条 ｜ 英文 {m['latin_pct']:.1f}% ｜ 每条例词中位 {m['token_median']}")
    print(f"  噪音：方法签名串 {m['method_calls']} ｜ XML标签 {m['xml_tags']}"
          f" ｜ 「」 {m['brackets']} ｜ 箭头 {m['arrows']}")

    hard_fail = []
    for k, label in HARD_ZERO.items():
        if m[k] != 0:
            hard_fail.append(f"{label}：{m[k]} 处（黄金案例 0）")
    for k, ((lo, hi), label) in HARD_BAND.items():
        v = m[k]
        if not (lo <= v <= hi):
            got = f"{v:.1f}" if isinstance(v, float) else str(v)
            hard_fail.append(f"{label}：{got}（黄金案例 {lo}–{hi}）")

    ref_notes = []
    for k, ((lo, hi), label) in REF_BAND.items():
        v = m[k]
        if not (lo <= v <= hi):
            got = f"{v:.1f}" if isinstance(v, float) else str(v)
            ref_notes.append(f"{label}：{got}（五案例落在 {lo}–{hi}，若 PDF 章节厚薄不同可忽略）")

    if hard_fail:
        print("\n  ✗ 硬信号出带，按 anti-patterns.md 逐条改：")
        for x in hard_fail:
            print(f"    · {x}")
    else:
        print("\n  ✓ 硬信号全部正常")

    if ref_notes:
        print("\n  ⚠ 体量参考（不强制）：")
        for x in ref_notes:
            print(f"    · {x}")

    skeleton_ok = all([p["has_title"], p["has_sub"], p["has_intro"], p["has_decl"],
                       p["has_fit"], p["has_kw"], p["has_deliver"], bool(p["groups"])])
    if not skeleton_ok:
        print("\n  ✗ 骨架有缺段，先补齐再谈密度")
        return False
    return not hard_fail


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(0 if report(sys.argv[1]) else 1)
