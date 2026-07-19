# -*- coding: utf-8
"""pinming-h-split39.xlsx 全明細_H付与 → sales-dashboard-2 lookup JSON."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

DEFAULT_XLSX = Path(r"C:\Users\Satoshi\Downloads\pinming-h-split39.xlsx")
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\pinming-h-split39-lookup.json")


def norm_desc(text: object) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return " ".join(str(text).strip().split()).lower()


def norm_name(text: object) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return str(text).strip()


def majority(counter: Counter[str]) -> tuple[str, int, int]:
    if not counter:
        return "", 0, 0
    pinming, n = counter.most_common(1)[0]
    return pinming, n, sum(counter.values())


def build(xlsx: Path, out: Path) -> dict:
    df = pd.read_excel(xlsx, sheet_name="全明細_H付与")
    df["Amount"] = pd.to_numeric(df.get("Amount"), errors="coerce").fillna(0)

    by_desc: dict[str, Counter[str]] = {}
    by_desc_ks: dict[str, Counter[str]] = {}
    by_ks_name: dict[str, Counter[str]] = {}
    by_ks_name_ks: dict[str, Counter[str]] = {}

    for _, row in df.iterrows():
        h = norm_name(row.get("H_新"))
        if not h:
            continue
        desc = norm_desc(row.get("Description"))
        ks_name = norm_name(row.get("KS品名"))
        amt = float(row.get("Amount") or 0)
        is_ks = amt > 0

        if desc:
            by_desc.setdefault(desc, Counter())[h] += 1
            if is_ks:
                by_desc_ks.setdefault(desc, Counter())[h] += 1
        if ks_name:
            by_ks_name.setdefault(ks_name, Counter())[h] += 1
            if is_ks:
                by_ks_name_ks.setdefault(ks_name, Counter())[h] += 1

    def pack(counter_map: dict[str, Counter[str]]) -> dict[str, str]:
        out_map: dict[str, str] = {}
        for key, counter in counter_map.items():
            pinming, maj, total = majority(counter)
            if pinming and maj == total:
                out_map[key] = pinming
        return out_map

    payload = {
        "source": str(xlsx),
        "byDescriptionExact": pack(by_desc_ks) or pack(by_desc),
        "byKsProductName": pack(by_ks_name_ks) or pack(by_ks_name),
        "meta": {
            "description_keys": len(by_desc),
            "description_exact_keys": len(pack(by_desc_ks) or pack(by_desc)),
            "ks_name_keys": len(by_ks_name),
            "ks_name_exact_keys": len(pack(by_ks_name_ks) or pack(by_ks_name)),
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    payload = build(args.xlsx, args.out)
    print(f"Wrote {args.out}")
    print(payload["meta"])


if __name__ == "__main__":
    main()
