# -*- coding: utf-8 -*-
"""KS_大中小分類リストから product_code→品名 を材料ルールで生成."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

DEFAULT_CSV = Path(
    r"E:\KSS-KSファイル集計\output\reports\KS_大中小分類リスト_20260718_153724.csv"
)
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\ks-product-code-pinming.json")

SKIP_MIDS = {"（KSS未对应）", "桐井自生产", "模具费", "色粉", "木纹转印", "运费"}

MID_DIRECT = {
    "不锈钢制天花板": "不锈钢框架天花",
    "不锈钢装饰槽": "不锈钢装饰槽",
    "特造铝制天花板": "特造铝制天花",
    "铁制天花板": "特造框架天花",
    "铁槽": "铁槽",
    "镀锌钢带": "镀锌钢带",
    "125mmMIP石膏组合间隔（1220#）": "MIP石膏组合间隔1220#",
    "125mmMIP石膏组合间隔（610#）": "MIP石膏组合间隔610#",
    "12MM普通纸面石膏板": "12mm普通纸面石膏板",
    "耐火纸面石膏板": "耐火纸面石膏板",
    "岩棉-B70": "岩棉-B50\\100KG",
    "岩棉-B75": "岩棉-Y50\\60KG",
    "铝方通": "铝方通",
    "KTA15铝铁主龙骨（桐井）": "KTA铝铁主骨",
    "KTA15铝铁长副龙骨（桐井）": "KTA铝铁长副骨",
    "KTA15铝铁短副龙骨（桐井）": "KTA铝铁短副骨",
    "铁长副龙骨(桐井）": "铁长副龙骨",
    "铁短副龙骨（桐井）": "铁短副龙骨",
    "铁主龙骨(桐井）": "铁主龙骨",
    "铁L角（桐井）": "铁L角",
    "铝制支架配件": "铝喷塑装饰配件",
}


def classify_stainless(name: str, blob: str) -> str:
    if re.search(r"不锈钢装饰槽|不锈钢槽", blob):
        return "不锈钢装饰槽"
    if re.search(r"天花|ceiling", blob, re.I):
        return "不锈钢框架天花"
    if re.search(r"支架|洗手台|底架|层板|压网", blob):
        return "不锈钢支架配件"
    return "不锈钢框装饰板"


def classify_alu_ceiling(name: str, blob: str) -> str:
    if re.search(r"铝方通|方通", blob):
        return "铝方通"
    if re.search(r"阔条天花|格子天花", blob):
        return "特造框架天花"
    if re.search(r"墙身板|企身板|蚀刻铝板|^铝板", blob) or re.search(r"铝墙身|铝企身", name):
        return "铝喷塑装饰板"
    if re.search(r"特造", blob):
        return "特造铝制天花"
    return "铝喷塑装饰板"


def classify_iron_frame(name: str, blob: str) -> str:
    if name == "铁制框架配件" or re.search(r"铁制框架配件", blob):
        return "铁制框架配件"
    if re.search(r"天地骨|天地结构|铁内弯地槽|铁地伏", blob):
        return "铁天地结构骨槽"
    if re.search(r"地槽|铁c槽|铁弧形槽|u型槽|c桥", blob):
        return "铁槽"
    if re.search(r"企筒|直边孔板|孔板|墙身板|铁板", blob):
        return "铁喷塑装饰板"
    if re.search(r"z骨|z型|十字|l码|装饰配件", blob):
        return "铁装饰配件"
    if re.search(r"竖骨|豎骨|横骨|中心骨|凹凸骨|挂骨|勾骨|吊码|衣架", blob):
        return "铁框架配件"
    return "铁框架配件"


def classify_board(name: str, blob: str) -> str | None:
    n = re.sub(r"\s+", "", blob.lower())
    if re.search(r"taishan\s*h\s*d\s*gf|hd\s*gf.*gypsum|gypsum.*board.*\bn\b|\(n板\)", blob, re.I):
        return "石膏基高性能纤维板(N板)"
    if re.search(r"waterproof.*gypsum|taishan.*waterproof", blob, re.I):
        return "耐水纸面石膏板"
    if re.search(r"fireproof.*gypsum|highdensity.*fireproof", n):
        return "耐火纸面石膏板"
    if re.search(r"highdensity.*gypsum(?!.*\bn\b)", n):
        return "石膏基高性能纤维板"
    if re.search(r"mkboardk|mk\s*board\s*k", n):
        return "12mm水泥纤维板-BOARD K"
    if re.search(r"9mm|1220mmx2440mmx9|1220×2440×9", n) and re.search(r"boardc|mkboardc", n):
        return "9mm水泥纤维板-BOARD C"
    if re.search(r"boardc|mkboardc|mk\s*board\s*c|水泥纤维板.*boardc", n):
        return "12mm水泥纤维板-BOARD C"
    if re.search(r"hd\s*gf.*gypsum.*\bn\b|gypsum.*board.*\bn\b|\(n板\)", blob, re.I):
        return "石膏基高性能纤维板(N板)"
    if re.search(r"87.?112|112.?87", blob):
        return "石膏基高性能纤维板(87\\112MM)"
    if re.search(r"墙板", blob) and re.search(r"石膏基|高性能", blob):
        return "石膏基高性能纤维板(墙板)"
    if re.search(r"mip.*610|610.*间隔|610#", blob, re.I):
        return "MIP石膏组合间隔610#"
    if re.search(r"mip.*1220|1220.*间隔|1220#|mip石膏板组合间隔", blob, re.I):
        return "MIP石膏组合间隔1220#"
    if re.search(r"石膏基高性能|高性能纤维|hd\s*gf|mip.*间隔|组合间隔", blob, re.I):
        return "石膏基高性能纤维板"
    if re.search(r"12\s*mm.*普通.*石膏", blob):
        return "12mm普通纸面石膏板"
    if re.search(r"耐水.*石膏|moisture.*gypsum|waterproof\s*gypsum", blob, re.I):
        return "耐水纸面石膏板"
    if re.search(r"耐火.*石膏|fire.*gypsum", blob, re.I):
        return "耐火纸面石膏板"
    if re.search(r"普通.*石膏|regular\s*gypsum|纸面石膏", blob, re.I):
        return "普通纸面石膏板"
    return None


def classify_row(mid: str, name: str, detail: str) -> str | None:
    mid = mid.strip()
    name = name.strip()
    blob = f"{name} {detail}".strip()
    if not mid and not blob:
        return None
    if mid in SKIP_MIDS:
        return None
    if mid == "12MM普通纸面石膏板":
        board = classify_board(name, blob)
        if board:
            return board
        return "12mm普通纸面石膏板"
    if mid == "铁制框架配件":
        return classify_iron_frame(name, blob)
    if mid == "不锈钢":
        return classify_stainless(name, blob)
    if mid == "铝制天花板":
        return classify_alu_ceiling(name, blob)
    if mid in MID_DIRECT:
        return MID_DIRECT[mid]
    board = classify_board(name, blob)
    if board:
        return board
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    df = pd.read_csv(args.csv, encoding="utf-8-sig", dtype=str).fillna("")
    by_code: dict[str, str] = {}
    meta: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = str(row.get("产品代码", "")).strip()
        if not code:
            continue
        mid = str(row.get("材料中分类", "")).strip()
        name = str(row.get("品名", "")).strip()
        detail = str(row.get("详细", "")).strip()
        pin = classify_row(mid, name, detail)
        if pin:
            by_code[code] = pin
            meta[code] = {"mid": mid, "name": name, "pinming": pin}

    payload = {
        "source": args.csv.name,
        "method": "material_rules_from_master_csv",
        "count": len(by_code),
        "byCode": by_code,
        "meta": meta,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(by_code)} codes -> {args.out}")


if __name__ == "__main__":
    main()
