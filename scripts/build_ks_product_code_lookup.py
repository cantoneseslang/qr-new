# -*- coding: utf-8 -*-
"""Build product_code lookup JSON for sales-dashboard from KS_大中小分類リスト."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REP = Path(r"E:\KSS-KSファイル集計\output\reports")
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\ks-product-code-lookup.json")


def find_latest_list_csv(rep: Path) -> Path:
    cands = sorted(rep.glob("KS_大中小分類リスト_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        raise FileNotFoundError(f"No KS_大中小分類リスト_*.csv under {rep}")
    return cands[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    src = args.csv or find_latest_list_csv(REP)
    df = pd.read_csv(src, encoding="utf-8-sig", dtype=str).fillna("")

    by_code: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        code = str(row.get("产品代码", "")).strip()
        if not code:
            continue
        by_code[code] = {
            "major": str(row.get("大分类", "")).strip(),
            "mid": str(row.get("材料中分类", "")).strip(),
            "productName": str(row.get("品名", "")).strip(),
            "spec": str(row.get("规格", "")).strip(),
            "thickness": str(row.get("板厚(mm)", "")).strip(),
            "detail": str(row.get("详细", "")).strip(),
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": src.name,
        "generatedFrom": str(src),
        "count": len(by_code),
        "byCode": by_code,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(by_code)} codes -> {args.out}")


if __name__ == "__main__":
    main()
