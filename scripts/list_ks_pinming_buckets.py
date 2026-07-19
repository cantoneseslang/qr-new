# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pandas as pd

HIER = Path(
    r"E:\KSS-KSファイル集計\output\reports\KS_指定12項目抽出_分類階層_20260718_153724.xlsx"
)
EXCL = Path(r"E:\sales-dashboard-2\data\ks-caiwu-excess-exclusions.json")
SALES = Path(r"E:\sales-dashboard-2")
BATCH = SALES / "scripts" / "classify-pinming-batch.ts"
MONTHS = [f"2026-{m:02d}" for m in range(1, 7)]
PAINT = re.compile(r"来料喷涂|喷涂加工|運費|运费")


def main() -> None:
    k = pd.read_excel(HIER, sheet_name="明细")
    k["Amount(HKD)"] = pd.to_numeric(k["Amount(HKD)"], errors="coerce").fillna(0)
    k["日期"] = pd.to_datetime(k["日期"], errors="coerce")
    k["month"] = k["日期"].dt.strftime("%Y-%m")
    k = k[k["month"].isin(MONTHS)].copy()
    k = k[~k["description"].astype(str).str.contains(PAINT, na=False)]
    if EXCL.exists():
        data = json.loads(EXCL.read_text(encoding="utf-8"))
        k = k[~k.index.isin(set(data.get("excluded_row_indices", [])))]
        keys = {
            (
                str(l.get("ks_doc_no", "")).upper(),
                str(l.get("delivery_list_no", "")).upper(),
                str(l.get("description", ""))[:80],
                round(float(l.get("amount_hkd", 0)), 2),
            )
            for l in data.get("lines", [])
        }
        k = k[
            ~k.apply(
                lambda r: (
                    str(r.get("單號", "")).upper(),
                    str(r.get("出貨清單號", "")).upper(),
                    str(r.get("description", ""))[:80],
                    round(float(r.get("Amount(HKD)", 0)), 2),
                )
                in keys,
                axis=1,
            )
        ]
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
    tmp = Path(r"E:\factory_monitoring_system\logs\_tmp_26list")
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
    mp = {x["id"]: x["pinming"] for x in json.loads(outp.read_text(encoding="utf-8"))}
    k["pinming"] = [mp[str(i)] for i in k.index]
    g = (
        k.groupby("pinming")
        .agg(rows=("Amount(HKD)", "count"), total=("Amount(HKD)", "sum"))
        .sort_values("total", ascending=False)
    )
    print(f"KS分類先: {len(g)} 種類")
    for i, (name, row) in enumerate(g.iterrows(), 1):
        print(f"{i:2}. {name} | {int(row.rows)}行 | {row.total:,.0f} HKD")


if __name__ == "__main__":
    main()
