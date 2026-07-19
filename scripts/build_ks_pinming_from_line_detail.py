# -*- coding: utf-8 -*-
"""
caiwu_ks_line_detail Excel（明細対比）から KS→佐近品名 の実績マップを生成する。

正本例:
  E:\\factory_monitoring_system\\logs\\caiwu_ks_line_detail_2026-01_2026-05_20260718_154355.xlsx

同一出荷で CAIWU↔KS が並んでいる行の C_品名 を、KS側 Description/品名 への教師データとして使う。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

DEFAULT_XLSX = Path(
    r"E:\factory_monitoring_system\logs\caiwu_ks_line_detail_2026-01_2026-05_20260718_154355.xlsx"
)
DEFAULT_OUT = Path(r"E:\sales-dashboard-2\data\ks-pinming-from-line-detail.json")

RE_MM_PREFIX = re.compile(r"^[\d.]+\s*mm", re.I)


def nonempty(v: object) -> bool:
    s = str(v or "").strip()
    return s not in ("", "nan", "None")


def ks_token_from_description(desc: str) -> str:
    s = str(desc or "").strip()
    if not s:
        return ""
    s = RE_MM_PREFIX.sub("", s).strip()
    return s.split()[0] if s else ""


def load_detail_sheet(xlsx: Path) -> pd.DataFrame:
    df = pd.read_excel(xlsx, sheet_name="明細対比", header=1)
    df = df.rename(
        columns={
            "Unnamed: 0": "状態",
            "Unnamed: 1": "月",
            "Unnamed: 2": "突合",
            "Unnamed: 3": "対比出货",
            "Unnamed: 4": "グループ金額差",
            "Unnamed: 5": "グループC合計",
            "Unnamed: 6": "グループK合計",
            "品名": "C_品名",
            "产品名称": "C_产品名称",
            "产品尺寸": "C_产品尺寸",
            "品名.1": "K_品名",
            "Description": "K_Description",
            "Amount": "K_Amount",
        }
    )
    for col in ("状態", "月", "突合", "対比出货", "グループ金額差", "グループC合計", "グループK合計"):
        if col in df.columns:
            df[col] = df[col].ffill()
    df["K_Amount"] = pd.to_numeric(df.get("K_Amount"), errors="coerce").fillna(0.0)
    return df


def pick_winner(counter: Counter, min_share: float = 0.55) -> tuple[str | None, float]:
    if not counter:
        return None, 0.0
    total = sum(counter.values())
    if total <= 0:
        return None, 0.0
    name, amt = counter.most_common(1)[0]
    share = amt / total
    if share >= min_share:
        return name, share
    return None, share


def classify_24t_keel(desc: str) -> str | None:
    n = re.sub(r"\s+", "", str(desc or "").lower())
    if "24t龙骨" not in n and "24t" not in n:
        return None
    if re.search(r"短副|600mm|2尺|1200mm|400mm|500mm|1500mm", n) and not re.search(
        r"3000|2400|10尺|8尺|4尺|主", n
    ):
        return "铁短副龙骨"
    if re.search(r"长副|3000mm|2400mm|10尺|3000", n):
        return "铁长副龙骨"
    if re.search(r"主|4尺|8尺|15t主|kt24主", n):
        return "铁主龙骨"
    return "铁主龙骨"


def build_map(df: pd.DataFrame) -> dict:
    matched = df[
        df["C_产品名称"].apply(nonempty) & df["K_Description"].apply(nonempty)
    ].copy()

    by_token: dict[str, Counter] = defaultdict(Counter)
    by_desc: dict[str, Counter] = defaultdict(Counter)
    samples: dict[str, list[str]] = defaultdict(list)

    for _, row in matched.iterrows():
        pinming = str(row.get("C_品名") or "").strip()
        if not nonempty(pinming) or pinming == "未分類":
            continue
        desc = str(row.get("K_Description") or "").strip()
        amt = float(row.get("K_Amount") or 0.0)
        if amt <= 0:
            continue

        token = ks_token_from_description(desc)
        if token:
            by_token[token][pinming] += amt
            if len(samples[token]) < 3:
                samples[token].append(desc[:80])

        # 24T龙骨は Description 長さで佐近品名分割
        keel = classify_24t_keel(desc)
        if keel:
            by_desc["__24T龙骨__"][keel] += amt

        # 完全一致 Description → 品名（高信頼・少数）
        norm_desc = re.sub(r"\s+", " ", desc).strip().lower()
        if norm_desc:
            by_desc[norm_desc][pinming] += amt

    token_map: dict[str, str] = {}
    token_meta: dict[str, dict] = {}
    for token, counter in by_token.items():
        winner, share = pick_winner(counter)
        if winner:
            token_map[token] = winner
            token_meta[token] = {
                "share": round(share, 4),
                "totalHkd": round(sum(counter.values()), 2),
                "top": counter.most_common(4),
                "samples": samples.get(token, []),
            }

    desc_map: dict[str, str] = {}
    desc_meta: dict[str, dict] = {}
    for desc, counter in by_desc.items():
        if desc == "__24T龙骨__":
            # handled separately
            continue
        winner, share = pick_winner(counter, min_share=0.85)
        if winner and sum(counter.values()) >= 5000:
            desc_map[desc] = winner
            desc_meta[desc] = {
                "share": round(share, 4),
                "totalHkd": round(sum(counter.values()), 2),
            }

    keel_map: dict[str, str] = {}
    if "__24T龙骨__" in by_desc:
        for pinming, amt in by_desc["__24T龙骨__"].most_common():
            if amt > 0:
                keel_map[pinming] = pinming

    return {
        "source": str(DEFAULT_XLSX.name),
        "matchedLines": int(len(matched)),
        "matchedAmountHkd": round(float(matched["K_Amount"].sum()), 2),
        "byKsToken": token_map,
        "byKsTokenMeta": token_meta,
        "byDescriptionExact": desc_map,
        "byDescriptionExactMeta": desc_meta,
        "keel24TNote": "24T龙骨 uses classify24TKeel on full Description at runtime",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.xlsx.exists():
        raise FileNotFoundError(args.xlsx)

    df = load_detail_sheet(args.xlsx)
    payload = build_map(df)
    payload["source"] = args.xlsx.name
    payload["generatedFrom"] = str(args.xlsx)
    payload["tokenCount"] = len(payload["byKsToken"])
    payload["descriptionExactCount"] = len(payload["byDescriptionExact"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Wrote {payload['tokenCount']} tokens, "
        f"{payload['descriptionExactCount']} exact desc -> {args.out}"
    )


if __name__ == "__main__":
    main()
