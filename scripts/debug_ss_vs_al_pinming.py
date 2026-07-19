# -*- coding: utf-8 -*-
"""不锈钢系が铝喷塑装饰板に誤分類されている行を洗い出す."""
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
SS = re.compile(r"不锈钢|不鏽鋼", re.I)
AL = re.compile(r"铝暗架|铝明架|铝制天花板|铝天花|铝跌级|铝双搭|铝弧形", re.I)


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
    tmp = Path(r"E:\factory_monitoring_system\logs\_tmp_ss_wrong")
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
    k = pd.read_excel(HIER, sheet_name="明细")
    k["Amount(HKD)"] = pd.to_numeric(k["Amount(HKD)"], errors="coerce").fillna(0)
    k["日期"] = pd.to_datetime(k["日期"], errors="coerce")
    k["month"] = k["日期"].dt.strftime("%Y-%m")
    k = k[k["month"].isin(MONTHS)].copy()
    k = k[~k["description"].astype(str).str.contains(PAINT, na=False)]
    k = classify(k)

    blob = (
        k["品名"].astype(str)
        + " "
        + k["description"].astype(str)
        + " "
        + k["材料中分类"].astype(str)
    )

    # 不锈钢框架天花 should be stainless CEILING (天花)
    ss_ceiling = k[
        blob.str.contains(SS)
        & blob.str.contains(re.compile(r"天花|ceiling", re.I))
        & (k["pinming"] != "不锈钢框架天花")
    ]
    print("=== 不锈钢+天花 なのに 不锈钢框架天花 以外 ===")
    print(f"行数 {len(ss_ceiling)}  金額 {ss_ceiling['Amount(HKD)'].sum():,.0f}")
    by = ss_ceiling.groupby("pinming")["Amount(HKD)"].sum().sort_values(ascending=False)
    for p, a in by.items():
        print(f"  -> {p}: {a:,.0f}")
    print()
    for _, r in ss_ceiling.sort_values("Amount(HKD)", ascending=False).head(15).iterrows():
        print(
            f"  {r['pinming']} | {r['Amount(HKD)']:,.0f} | {r.get('产品代码','')} | {r.get('材料中分类','')} | {str(r.get('description',''))[:55]}"
        )

    # 不锈钢 anything -> 铝喷塑装饰板
    ss_to_al = k[blob.str.contains(SS) & (k["pinming"] == "铝喷塑装饰板")]
    print()
    print("=== 不锈钢系 → 铝喷塑装饰板（材料完全に違う）===")
    print(f"行数 {len(ss_to_al)}  金額 {ss_to_al['Amount(HKD)'].sum():,.0f}")
    for _, r in ss_to_al.sort_values("Amount(HKD)", ascending=False).head(20).iterrows():
        print(
            f"  {r['Amount(HKD)']:,.0f} | {r.get('产品代码','')} | {r.get('品名','')} | {r.get('材料中分类','')} | {str(r.get('description',''))[:50]}"
        )

    # 铝天花 -> wrong buckets
    al_ceiling = k[blob.str.contains(AL) & (k["pinming"].isin(["铁喷塑装饰板", "铁框架配件", "铁槽"]))]
    print()
    print("=== 铝天花 → 铁系（別の誤分類）===")
    print(f"行数 {len(al_ceiling)}  金額 {al_ceiling['Amount(HKD)'].sum():,.0f}")


if __name__ == "__main__":
    main()
