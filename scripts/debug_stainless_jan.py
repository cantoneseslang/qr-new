# -*- coding: utf-8 -*-
"""Find KS lines for Jan that should be 不锈钢框架天花 but aren't."""
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
PAINT = re.compile(r"来料喷涂|喷涂加工|運費|运费")
STAINLESS = re.compile(
    r"不锈钢|不鏽鋼|SS\s|stainless|暗架天花|不锈钢制|不锈钢框",
    re.I,
)


def load_ks_jan() -> pd.DataFrame:
    k = pd.read_excel(HIER, sheet_name="明细")
    k["Amount(HKD)"] = pd.to_numeric(k["Amount(HKD)"], errors="coerce").fillna(0)
    k["日期"] = pd.to_datetime(k["日期"], errors="coerce")
    k["month"] = k["日期"].dt.strftime("%Y-%m")
    k = k[k["month"] == "2026-01"].copy()
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
    return k


def classify(k: pd.DataFrame) -> pd.DataFrame:
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
    tmp = Path(r"E:\factory_monitoring_system\logs\_tmp_stainless_jan")
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
    k = k.copy()
    k["pinming"] = [mp[str(i)] for i in k.index]
    return k


def main() -> None:
    k = classify(load_ks_jan())
    ss = k[k["pinming"] == "不锈钢框架天花"]
    print(f"Already 不锈钢框架天花: {len(ss)} lines, {ss['Amount(HKD)'].sum():,.0f} HKD")
    for _, r in ss.iterrows():
        print(
            f"  {r['Amount(HKD)']:,.0f} | {r.get('产品代码','')} | {r.get('材料中分类','')} | {str(r.get('description',''))[:60]}"
        )

    mask = k["pinming"] != "不锈钢框架天花"
    hint = (
        k["description"].astype(str).str.contains(STAINLESS, na=False)
        | k["品名"].astype(str).str.contains(STAINLESS, na=False)
        | k["材料中分类"].astype(str).str.contains("不锈钢", na=False)
        | k["材料中分类"].astype(str).str.contains("不鏽", na=False)
    )
    cand = k[mask & hint].sort_values("Amount(HKD)", ascending=False)

    print(f"\nStainless-like but NOT 不锈钢框架天花: {len(cand)} lines, {cand['Amount(HKD)'].sum():,.0f} HKD")
    for _, r in cand.head(30).iterrows():
        print(
            f"  -> {r['pinming']} | {r['Amount(HKD)']:,.0f} | {r.get('产品代码','')} | {r.get('材料中分类','')} | {str(r.get('description',''))[:55]}"
        )

    # Also check 特造框架天花 with stainless hints
    tz = k[(k["pinming"] == "特造框架天花") & k["description"].astype(str).str.contains("不锈钢|不鏽", na=False)]
    print(f"\n特造框架天花 with 不锈钢 in desc: {len(tz)} lines, {tz['Amount(HKD)'].sum():,.0f} HKD")
    for _, r in tz.head(20).iterrows():
        print(
            f"  {r['Amount(HKD)']:,.0f} | {r.get('产品代码','')} | {str(r.get('description',''))[:60]}"
        )


if __name__ == "__main__":
    main()
