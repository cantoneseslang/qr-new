# -*- coding: utf-8
"""pinming-h-split39.xlsx → 月×品名 KS金額 JSON（ダッシュボード正本数字）."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

DEFAULT_XLSX = Path(r"C:\Users\Satoshi\Downloads\pinming-h-split39.xlsx")
DEFAULT_CSV = Path(r"C:\Users\Satoshi\Downloads\pinming-39-list.csv")
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\pinming-h-split39-monthly-ks.json")
DEFAULT_LOOKUP_OUT = Path(r"E:\sales-dashboard-2\data\pinming-h-split39-lookup.json")


def load_display_order(csv_path: Path) -> list[str]:
    with csv_path.open(encoding="utf-8-sig") as f:
        return [row["H_品名"] for row in csv.DictReader(f)]


def normalize_h(h: str, order: list[str]) -> str:
    h = str(h or "").strip()
    if not h:
        return "未分類"
    if h in order:
        return h
    aliases = {
        "12mm普通纸面石膏板": "普通纸面石膏板",
        "水泥纤维板-BOARD C": "9mm水泥纤维板-BOARD C",
    }
    return aliases.get(h, "未分類")


def build_monthly(xlsx: Path, csv_path: Path, out: Path) -> dict:
    order = load_display_order(csv_path)
    df = pd.read_excel(xlsx, sheet_name="全明細_H付与")
    df["Amount"] = pd.to_numeric(df.get("Amount"), errors="coerce").fillna(0)
    ks = df[df["Amount"] > 0].copy()

    by_month: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for _, row in ks.iterrows():
        month = str(row.get("月") or "").strip()
        if not month or month == "nan":
            continue
        h = normalize_h(row.get("H_新"), order)
        by_month[month][h] += float(row["Amount"])

    months_sorted = sorted(by_month.keys())
    payload = {
        "source": str(xlsx),
        "displayOrder": order,
        "months": {
            m: {cat: round(by_month[m].get(cat, 0.0), 2) for cat in order + ["未分類"]}
            for m in months_sorted
        },
        "meta": {
            "ks_row_count": int(len(ks)),
            "ks_amount_total": round(float(ks["Amount"].sum()), 2),
            "months": months_sorted,
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    import argparse

    from build_pinming_h_split39_lookup import build as build_lookup

    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--lookup-out", type=Path, default=DEFAULT_LOOKUP_OUT)
    args = ap.parse_args()

    build_lookup(args.xlsx, args.lookup_out)
    payload = build_monthly(args.xlsx, args.csv, args.out)
    print(f"Wrote {args.out}")
    print(f"Wrote {args.lookup_out}")
    print(payload["meta"])


if __name__ == "__main__":
    main()
