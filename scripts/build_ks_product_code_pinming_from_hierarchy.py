# -*- coding: utf-8 -*-
"""Build product_code -> pinming from hierarchy 明细 (actual KS lines), not list 品名 only."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

HIER = Path(
    r"E:\KSS-KSファイル集計\output\reports\KS_指定12項目抽出_分類階層_20260718_153724.xlsx"
)
EXCL = Path(r"E:\sales-dashboard-2\data\ks-caiwu-excess-exclusions.json")
SALES = Path(r"E:\sales-dashboard-2")
BATCH = SALES / "scripts" / "classify-pinming-batch.ts"
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\ks-product-code-pinming.json")
PAINT = ("来料喷涂", "喷涂加工", "运费", "運費")


def classify_batch(req: list[dict]) -> dict[str, str]:
    tmp = Path(r"E:\factory_monitoring_system\logs\_tmp_pinming_build")
    tmp.mkdir(exist_ok=True)
    inp, outp = tmp / "in.json", tmp / "out.json"
    inp.write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    exe = "npx.cmd" if os.name == "nt" else "npx"
    proc = subprocess.run(
        [exe, "--yes", "tsx", str(BATCH), str(inp), str(outp)],
        cwd=str(SALES),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=os.name == "nt",
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout)
    return {r["id"]: r["pinming"] for r in json.loads(outp.read_text(encoding="utf-8"))}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    k = pd.read_excel(HIER, sheet_name="明细")
    k["Amount(HKD)"] = pd.to_numeric(k["Amount(HKD)"], errors="coerce").fillna(0)
    k["日期"] = pd.to_datetime(k["日期"], errors="coerce")
    k = k[k["日期"].dt.strftime("%Y-%m").between("2026-01", "2026-06")].copy()

    if EXCL.exists():
        data = json.loads(EXCL.read_text(encoding="utf-8"))
        excl_idx = set(data.get("excluded_row_indices", []))
        k = k[~k.index.isin(excl_idx)]
    k = k[~k["description"].astype(str).str.contains("|".join(PAINT), na=False)]

    req = []
    for i, r in k.iterrows():
        req.append(
            {
                "id": str(i),
                "product_name": None if pd.isna(r.get("品名")) else r.get("品名"),
                "description": None if pd.isna(r.get("description")) else r.get("description"),
                "mid_category": None if pd.isna(r.get("材料中分类")) else r.get("材料中分类"),
                "product_code": None if pd.isna(r.get("产品代码")) else r.get("产品代码"),
            }
        )
    mp = classify_batch(req)
    k["pinming"] = [mp[str(i)] for i in k.index]

    by_code: dict[str, Counter] = defaultdict(Counter)
    for _, r in k.iterrows():
        code = str(r.get("产品代码") or "").strip()
        if not code:
            continue
        by_code[code][str(r["pinming"])] += float(r["Amount(HKD)"])

    out_map: dict[str, str] = {}
    meta: dict[str, dict] = {}
    for code, cnt in by_code.items():
        pin, amt = cnt.most_common(1)[0]
        total = sum(cnt.values())
        out_map[code] = pin
        meta[code] = {
            "share": round(amt / total, 4) if total else 0,
            "totalHkd": round(total, 2),
            "top": cnt.most_common(3),
        }

    payload = {
        "sourceHierarchy": HIER.name,
        "count": len(out_map),
        "byCode": out_map,
        "meta": meta,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out_map)} codes from hierarchy lines -> {args.out}")


if __name__ == "__main__":
    main()
