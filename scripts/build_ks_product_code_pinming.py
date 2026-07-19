# -*- coding: utf-8 -*-
"""Build product_code -> 佐近品名 map from 大中小分類リスト + line_detail + 佐近整合ルール."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

REP = Path(r"E:\KSS-KSファイル集計\output\reports")
LINE_DETAIL = Path(
    r"E:\factory_monitoring_system\logs\caiwu_ks_line_detail_2026-01_2026-05_20260718_154355.xlsx"
)
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\ks-product-code-pinming.json")

ALIASES = {
    "不锈钢框架天花": "特造框架天花",
    "铁天地结构骨槽": "铁槽",
    "铁制框架配件": "铁框架配件",
    "不锈钢框装饰板": "铝喷塑装饰板",
    "MIP石膏组合间隔610#": "石膏基高性能纤维板",
    "MIP石膏组合间隔1220#": "石膏基高性能纤维板",
    "12mm水泥纤维板-BOARD K": "12mm水泥纤维板-BOARD C",
    "12mm普通纸面石膏板": "普通纸面石膏板",
    "水泥纤维板-BOARD C": "12mm水泥纤维板-BOARD C",
}

SKIP_TOKENS = re.compile(r"来料喷涂|喷涂加工|运费|運費|贴膜|包装用", re.I)


def finalize(pinming: str) -> str:
    return ALIASES.get(pinming, pinming)


def classify_24t(name: str, desc: str = "") -> str:
    n = re.sub(r"\s+", "", f"{name} {desc}").lower()
    if "24t" not in n and "24t龙骨" not in n:
        return ""
    if re.search(r"短副|600mm|2尺|1200mm|400mm|500mm|1500mm", n) and not re.search(
        r"3000|2400|10尺|8尺|4尺|主", n
    ):
        return "铁短副龙骨"
    if re.search(r"长副|3000mm|2400mm|10尺|3000", n):
        return "铁长副龙骨"
    return "铁主龙骨"


def classify_name(name: str, mid: str = "", desc: str = "") -> str:
    name = (name or "").strip()
    mid = (mid or "").strip()
    blob = f"{name} {desc}".strip()

    if not name and not desc:
        return "未分類"
    if SKIP_TOKENS.search(blob):
        return "未分類"

    k24 = classify_24t(name, desc)
    if k24:
        return finalize(k24)

    exact = {
        "铁竖骨": "铁框架配件",
        "铁横骨": "铁框架配件",
        "铁中心骨": "铁框架配件",
        "铁天地骨": "铁槽",
        "铁地槽": "铁槽",
        "铁地伏": "铁槽",
        "铁C槽": "铁槽",
        "铁C型槽": "铁槽",
        "铁L角": "铁L角",
        "镀锌带": "镀锌钢带",
        "铝方通": "铝方通",
        "Typical Panel": "铝喷塑装饰板",
        "Non-Typical Panel": "铝喷塑装饰板",
        "Stainless Steel cladding": "铝喷塑装饰板",
    }
    if name in exact:
        return finalize(exact[name])

    if "阔条天花" in blob or name.startswith("阔条天花"):
        return "特造框架天花"
    if "格子天花" in blob:
        return "特造框架天花"
    if "铁双搭天花" in blob:
        return "特造框架天花"
    if "铝明架天花" in blob or name == "铝明架天花":
        return "特造铝制天花"
    if "MK Board C" in blob or name.startswith("MK Board"):
        if re.search(r"\b9\s*mm|x\s*9mm|×9mm", blob, re.I):
            return "9mm水泥纤维板-BOARD C"
        return "12mm水泥纤维板-BOARD C"
    if "Taishan" in blob and "N" in blob:
        return "石膏基高性能纤维板(N板)"
    if "Taishan Regular" in blob or "普通纸面石膏板" in mid:
        return "普通纸面石膏板"
    if "Welltone" in blob and "100" in blob:
        return "岩棉-B50\\100KG"
    if "Welltone" in blob and ("60" in blob or "Y50" in blob):
        return "岩棉-Y50\\60KG"

    if mid == "铁制天花板" or mid == "不锈钢制天花板" or "不锈钢" in name and "天花" in blob:
        return "特造框架天花"
    if mid == "铁制框架配件":
        if re.search(r"天地骨|地槽|地伏", blob):
            return "铁槽"
        if re.search(r"企筒|直边孔板|孔板|墙身板", blob):
            return "铁喷塑装饰板"
        if re.search(r"z骨|十字|l码", blob, re.I):
            return "铁装饰配件"
        return "铁框架配件"
    if mid == "铁槽" or name in ("铝U型槽",):
        return "铁槽"
    if mid in ("铝方通", "铝冲孔方通", "铝波浪方通", "铝通"):
        return "铝方通"
    if mid == "镀锌钢带":
        return "镀锌钢带"
    if mid in ("铁L角（桐井）",):
        return "铁L角"
    if mid in ("12MM普通纸面石膏板",):
        return "普通纸面石膏板"
    if mid in ("耐火纸面石膏板",):
        return "耐火纸面石膏板"
    if mid in ("岩棉-B75",):
        return "岩棉-Y50\\60KG"
    if mid in ("岩棉-B70",):
        return "岩棉-B50\\100KG"
    if mid.startswith("125mmMIP"):
        return "石膏基高性能纤维板"
    if mid in ("KTA15铝铁主龙骨（桐井）",):
        return "KTA铝铁主骨"
    if mid in ("KTA15铝铁长副龙骨（桐井）",):
        return "KTA铝铁长副骨"
    if mid in ("KTA15铝铁短副龙骨（桐井）",):
        return "KTA铝铁短副骨"
    if mid in ("铁长副龙骨(桐井）",):
        return "铁长副龙骨"
    if mid in ("铁短副龙骨（桐井）",):
        return "铁短副龙骨"
    if mid in ("铁主龙骨(桐井）",):
        return "铁主龙骨"
    if mid == "龙骨(桐井）":
        return classify_24t(name, desc) or "铁主龙骨"

    if mid == "铝制天花板" or ("铝" in name and "天花" in blob):
        if "方通" in blob:
            return "铝方通"
        return "铝喷塑装饰板"

    if mid.startswith("铝") and mid not in ("铝制天花板",):
        if any(x in mid for x in ("角", "槽", "风咀", "支架", "配件", "收边", "灯", "框", "盖", "片")):
            return "铝喷塑装饰配件"
        return "铝喷塑装饰板"

    if "石膏" in blob:
        if "N" in blob:
            return "石膏基高性能纤维板(N板)"
        return "石膏基高性能纤维板"
    if "岩棉" in blob or "Rock Wool" in blob:
        return "岩棉-B50\\100KG" if "100" in blob else "岩棉-Y50\\60KG"

    return "未分類"


def load_token_overrides(xlsx: Path) -> dict[str, str]:
    """line_detail 明細対比: K Description token -> C_品名 (dominant, share>=70%)."""
    from collections import Counter, defaultdict

    df = pd.read_excel(xlsx, sheet_name="明細対比", header=1)
    df = df.rename(
        columns={
            "品名": "C_品名",
            "产品名称": "C_产品名称",
            "Description": "K_Description",
            "Amount": "K_Amount",
        }
    )
    df["K_Amount"] = pd.to_numeric(df["K_Amount"], errors="coerce").fillna(0)
    matched = df[
        (df["C_产品名称"].astype(str).str.len() > 1)
        & (df["K_Description"].astype(str).str.len() > 1)
    ]
    by: dict[str, Counter] = defaultdict(Counter)
    for _, r in matched.iterrows():
        c = str(r["C_品名"]).strip()
        d = str(r["K_Description"]).strip()
        if c in ("", "nan", "未分類"):
            continue
        tok = re.sub(r"^[\d.]+\s*mm", "", d, flags=re.I).strip().split()[0]
        if not tok or SKIP_TOKENS.search(tok):
            continue
        by[tok][c] += float(r["K_Amount"])

    out: dict[str, str] = {}
    for tok, cnt in by.items():
        total = sum(cnt.values())
        if total < 3000:
            continue
        pin, amt = cnt.most_common(1)[0]
        if amt / total >= 0.7:
            out[tok] = finalize(pin)
    # 佐近整合で上書き（C_品名が佐近とズレるもの）
    sakin_fix = {
        "铝暗架天花": "铝喷塑装饰板",
        "铝跌级天花": "铝喷塑装饰板",
        "铝双搭天花": "铝喷塑装饰板",
        "铝弧形天花": "铝喷塑装饰板",
        "铝H骨天花": "铝喷塑装饰板",
        "铝勾挂天花": "铝喷塑装饰板",
        "铝蛋格天花": "铝喷塑装饰板",
        "铝拉网天花": "铝喷塑装饰板",
        "24T龙骨": "",  # length split handles
        "KTA15龙骨": "铁框架配件",
        "铁天地骨": "铁槽",
        "铝U型槽": "铁槽",
        "铝明架天花": "特造铝制天花",
        "铝阔条天花": "特造框架天花",
        "阔条天花": "特造框架天花",
        "铁双搭天花": "特造框架天花",
        "Typical": "铝喷塑装饰板",
        "Non-Typical": "铝喷塑装饰板",
        "Stainless": "铝喷塑装饰板",
    }
    for k, v in sakin_fix.items():
        if v:
            out[k] = v
        elif k in out:
            del out[k]
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--line-detail", type=Path, default=LINE_DETAIL)
    args = parser.parse_args()

    list_csv = sorted(REP.glob("KS_大中小分類リスト_*.csv"), key=lambda p: p.stat().st_mtime)[-1]
    df = pd.read_csv(list_csv, encoding="utf-8-sig", dtype=str).fillna("")
    tokens = load_token_overrides(args.line_detail) if args.line_detail.exists() else {}

    by_code: dict[str, str] = {}
    for _, row in df.iterrows():
        code = str(row.get("产品代码", "")).strip()
        if not code:
            continue
        name = str(row.get("品名", "")).strip()
        mid = str(row.get("材料中分类", "")).strip()
        tok = re.sub(r"^[\d.]+\s*mm", "", name, flags=re.I).strip().split()[0] if name else ""
        pin = tokens.get(tok) or tokens.get(name) or classify_name(name, mid)
        by_code[code] = finalize(pin)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sourceList": list_csv.name,
        "sourceLineDetail": args.line_detail.name if args.line_detail.exists() else None,
        "count": len(by_code),
        "tokenOverrides": len(tokens),
        "byCode": by_code,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(by_code)} codes ({len(tokens)} tokens) -> {args.out}")


if __name__ == "__main__":
    main()
