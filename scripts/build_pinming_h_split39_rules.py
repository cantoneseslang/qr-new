# -*- coding: utf-8 -*-
"""pinming-h-split39.xlsx → sales-dashboard-2/data/pinming-h-split39-rules.json"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

DEFAULT_XLSX = Path(r"C:\Users\Satoshi\Downloads\pinming-h-split39.xlsx")
DEFAULT_CSV = Path(r"C:\Users\Satoshi\Downloads\pinming-39-list.csv")
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\pinming-h-split39-rules.json")
DEFAULT_LIST_OUT = Path(r"E:\sales-dashboard-2\data\pinming-39-list.json")


def norm_key(text: object) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def build_display_list(csv_path: Path, out: Path) -> list[str]:
    import csv as csv_mod

    with csv_path.open(encoding="utf-8-sig") as f:
        order = [row["H_品名"] for row in csv_mod.DictReader(f)]
    payload = {"source": csv_path.name, "order": order}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return order


def build(xlsx: Path, out: Path) -> dict:
    rules = pd.read_excel(xlsx, sheet_name="ルール一覧")
    names39 = [
        str(x)
        for x in pd.read_excel(xlsx, sheet_name="39品名一覧").iloc[:, 1].dropna()
    ]

    m_df = rules[rules["source"] == "M"][["key", "h_pinming", "confidence", "ambiguous"]].drop_duplicates(
        "key"
    )
    ae_df = rules[rules["source"] == "AE_prefix"][
        ["key", "h_pinming", "confidence", "ambiguous"]
    ].drop_duplicates("key")
    w_df = rules[rules["source"] == "W"][["key", "h_pinming"]].drop_duplicates("key")
    mn_df = rules[rules["source"] == "M_norm"][
        ["key", "h_pinming", "confidence", "ambiguous"]
    ].drop_duplicates("key")

    ae_sorted = ae_df.sort_values("key", key=lambda s: s.str.len(), ascending=False)

    payload = {
        "pinming39": names39,
        "m_exact": {str(r["key"]): str(r["h_pinming"]) for _, r in m_df.iterrows()},
        "m_norm": {norm_key(r["key"]): str(r["h_pinming"]) for _, r in mn_df.iterrows()},
        "ae_prefix": [
            [str(r["key"]), str(r["h_pinming"])] for _, r in ae_sorted.iterrows()
        ],
        "w_map": {str(r["key"]): str(r["h_pinming"]) for _, r in w_df.iterrows()},
        "meta": {
            "source": str(xlsx),
            "note": "別名統合なし（pinming-h-split39.xlsx ルール一覧より）",
            "counts": {
                "m_exact": len(m_df),
                "m_norm": len(mn_df),
                "ae_prefix": len(ae_df),
                "w_map": len(w_df),
            },
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--list-out", type=Path, default=DEFAULT_LIST_OUT)
    args = ap.parse_args()
    payload = build(args.xlsx, args.out)
    order = build_display_list(args.csv, args.list_out)
    print(f"Wrote {args.out}")
    print(f"Wrote {args.list_out} ({len(order)} items)")
    print("counts:", payload["meta"]["counts"])


if __name__ == "__main__":
    main()
