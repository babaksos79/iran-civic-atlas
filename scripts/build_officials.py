#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
بازتولید data/officials.csv از فایل‌های فصل ۹ (docs/03-officials/09-unit-files/*.md)

ورودی:  جدول‌های مارک‌داون با ستون‌های
        استان | شهرستان | سمت | نام | تاریخ انتصاب | منبع | وضع
خروجی:  data/officials.csv (UTF-8 با BOM، مانند بقیهٔ خروجی‌های data/)

نکتهٔ سازوکار: خواندن این فایل‌ها توسط انسان/پژوهشگر انجام شده و نام‌ها را اسکریپت
نمی‌سازد؛ این اسکریپت فقط دادهٔ ثبت‌شده را جمع می‌زند و آمار پوشش را گزارش می‌کند
تا هر به‌روزرسانی دستی بلافاصله در CSV منعکس شود.
"""
from __future__ import annotations

import csv
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIT_DIR = os.path.join(ROOT, "docs", "03-officials", "09-unit-files")
OUT_CSV = os.path.join(ROOT, "data", "officials.csv")

HEADER = [
    "province",
    "unit",
    "role",
    "name",
    "appointed",
    "source",
    "status",
    "deputy_official",   # جانشین رسمی (طبق قانون/مقررات — هنوز پر نشده)
    "deputies_probable", # جانشینان احتمالی — هنوز پر نشده
    "last_updated",
    "source_file",
]
STATUS_MAP = {"✅": "confirmed", "⚠️": "disputed", "⏳": "pending"}
LAST_UPDATED = "1405/08/30"  # ۳۰ آبان ۱۴۰۵


def split_row(line: str) -> list[str]:
    """جدول مارک‌داون را به سلول‌ها می‌شکند (بدون در نظر گرفتن | داخل متن نقل‌قول)."""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c)


PROVINCE_H = re.compile(r"^##\s+استان\s+(.+?)(?:\s+—.*)?$")
PROVINCE_H2 = re.compile(r"^##\s+(.+?)(?:\s+—\s+کد.*)?$")


def parse_file(path: str) -> list[dict]:
    """
    دو قالب در فایل‌های فصل ۹ پذیرفته می‌شود:
      ۱) جدول هفت‌ستونه: استان | شهرستان | سمت | نام | تاریخ | منبع | وضع
      ۲) جدول پنج‌ستونهٔ داخل بخش «## استان X»: سمت | نام | تاریخ | منبع | وضع
    """
    rows: list[dict] = []
    fname = os.path.basename(path)
    province_ctx = ""
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.startswith("##"):
                m = PROVINCE_H.match(line) or PROVINCE_H2.match(line)
                if m:
                    province_ctx = m.group(1).strip()
                continue
            if not line.startswith("|"):
                continue
            cells = split_row(line)
            if len(cells) < 5 or is_separator(cells):
                continue
            if len(cells) == 5:
                # قالب کوتاه: سمت | نام | تاریخ | منبع | وضع
                # (نام شهرستان از روی «سمت» بازسازی می‌شود: «فرماندار ری» ← ری)
                if cells[0] in {"سمت", ""}:
                    continue
                province = province_ctx
                role, name, appointed, source, status = cells
                if "استاندار" in role:
                    unit = province
                else:
                    unit = re.sub(
                        r"^(سرپرست\s+فرمانداری|فرمانداری|فرماندار|سرپرست)\s*",
                        "",
                        role,
                    )
                    unit = unit.replace("(سرپرست)", "").replace("ویژه", "").strip()
                    unit = unit or province
            else:
                province, unit, role, name, appointed, source, status = (cells + [""] * 7)[:7]
                if role in {"سمت", ""}:
                    continue
                if not province:
                    province = province_ctx
            m = re.search(r"(✅|⚠️|⏳)", status)
            flag = m.group(1) if m else ""
            rows.append(
                {
                    "province": province,
                    "unit": unit,
                    "role": role,
                    "name": name,
                    "appointed": appointed,
                    "source": source,
                    "status": STATUS_MAP.get(flag, "unknown"),
                    "deputy_official": "",
                    "deputies_probable": "",
                    "last_updated": LAST_UPDATED,
                    "source_file": fname,
                }
            )
    return rows


def main() -> int:
    if not os.path.isdir(UNIT_DIR):
        print(f"missing: {UNIT_DIR}", file=sys.stderr)
        return 1
    files = sorted(glob.glob(os.path.join(UNIT_DIR, "*.md")))
    all_rows: list[dict] = []
    per_file: dict[str, int] = {}
    for path in files:
        if os.path.basename(path) in {"README.md", "index.md"}:
            continue
        rows = parse_file(path)
        per_file[os.path.basename(path)] = len(rows)
        all_rows.extend(rows)

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(all_rows)

    # گزارش پوشش
    provinces = sorted({r["province"] for r in all_rows})
    governors = [r for r in all_rows if r["role"] == "استاندار"]
    county_rows = [r for r in all_rows if r["role"] != "استاندار"]
    by_status = {}
    for r in all_rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    print(f"files: {len(per_file)}")
    for name, n in per_file.items():
        print(f"  {name}: {n}")
    print(f"rows: {len(all_rows)}")
    print(f"provinces with entries: {len(provinces)} / 31")
    print(f"governors rows: {len(governors)} / 31")
    print(f"county rows: {len(county_rows)} / 484")
    print("status counts:", by_status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
