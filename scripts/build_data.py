#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
سازندهٔ داده‌های فاز ۱ پروژهٔ iran-civic-atlas
ورودی:  vendor/IranCountryDivisions/iran.csv   (دادهٔ رسمی مرکز آمار ایران، سال ۱۴۰۴)
خروجی:  data/*.csv  +  docs/01-divisions/03-tree/*.md  +  data/settlements/*.csv
"""
import csv, os, collections, io

SRC = "vendor/IranCountryDivisions/iran.csv"
DATA = "data"
TREE = "docs/01-divisions/03-tree"
SETT = os.path.join(DATA, "settlements")

TYPE_NAME = {
    "0": "کشور", "1": "استان", "2": "شهرستان", "3": "بخش",
    "4": "دهستان", "5": "شهر", "6": "آبادی", "7": "منطقه شهری",
}

os.makedirs(DATA, exist_ok=True)
os.makedirs(TREE, exist_ok=True)
os.makedirs(SETT, exist_ok=True)

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
by_id = {r["Id"]: r for r in rows}
children = collections.defaultdict(list)
for r in rows:
    children[r["ParentCountryDivisionId"]].append(r)

def path_of(node):
    """مسیر کامل از ریشه تا این گره"""
    parts = []
    cur = node
    while cur and cur["ParentCountryDivisionId"]:
        cur = by_id[cur["ParentCountryDivisionId"]]
        parts.append(cur["Name"])
    return list(reversed(parts))

def ancestors_by_type(node):
    """نام هر سطح بالادستی، به تفکیک نوع: {"1": استان, "2": شهرستان, ...}"""
    out = {}
    cur = node
    while cur and cur["ParentCountryDivisionId"]:
        cur = by_id[cur["ParentCountryDivisionId"]]
        if cur["DivisionType"] in ("1", "2", "3", "4", "5"):
            out[cur["DivisionType"]] = cur["Name"]
    return out

def sett_row(node):
    a = ancestors_by_type(node)
    parent = by_id[node["ParentCountryDivisionId"]]
    holder = a.get("4") or ("(زیر شهر " + parent["Name"] + ")" if parent["DivisionType"] in ("5", "7") else "")
    return [a.get("1", ""), a.get("2", ""), a.get("3", ""), holder, node["Code"], node["Name"]]

def ordered(kids, key=None):
    return sorted(kids, key=lambda r: (r["Code"], r["Name"]))

root = by_id["1"]
provinces = ordered(children["1"])

# ---------------------------------------------------------------- کپی دادهٔ کامل
with open(SRC, encoding="utf-8-sig") as f:
    raw = f.read()
with open(os.path.join(DATA, "divisions-1404.csv"), "w", encoding="utf-8") as f:
    f.write(raw)

# ---------------------------------------------------------------- CSV هر سطح
def write_csv(fname, header, out_rows):
    with open(os.path.join(DATA, fname), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(out_rows)

prov_rows = []
county_rows = []
district_rows = []
dehestan_rows = []
city_rows = []
urban_rows = []

# آبادی‌ها: مستقل از حلقهٔ بالا، چون والدشان می‌تواند دهستان یا شهر باشد
all_sett = [r for r in rows if r["DivisionType"] == "6"]

for p in provinces:
    prov_rows.append([p["Code"], p["Name"], p["Id"]])
    for c in ordered(children[p["Id"]]):
        county_rows.append([p["Code"], p["Name"], c["Code"], c["Name"], c["Id"]])
        for d in ordered(children[c["Id"]]):
            district_rows.append([p["Name"], c["Name"], d["Code"], d["Name"], d["Id"]])
            for sub in ordered(children[d["Id"]]):
                if sub["DivisionType"] == "4":
                    dehestan_rows.append([p["Name"], c["Name"], d["Name"], sub["Code"], sub["Name"], sub["Id"]])
                elif sub["DivisionType"] == "5":
                    city_rows.append([p["Name"], c["Name"], d["Name"], sub["Code"], sub["Name"], sub["Id"]])
                    for z in ordered(children[sub["Id"]]):
                        if z["DivisionType"] == "7":
                            urban_rows.append([p["Name"], c["Name"], d["Name"], sub["Name"], z["Code"], z["Name"]])


write_csv("provinces.csv", ["کد استان", "نام استان", "شناسه"], prov_rows)
write_csv("counties.csv", ["کد استان", "نام استان", "کد شهرستان", "نام شهرستان", "شناسه"], county_rows)
write_csv("districts.csv", ["استان", "شهرستان", "کد بخش", "نام بخش", "شناسه"], district_rows)
write_csv("dehestans.csv", ["استان", "شهرستان", "بخش", "کد دهستان", "نام دهستان", "شناسه"], dehestan_rows)
write_csv("cities.csv", ["استان", "شهرستان", "بخش", "کد شهر", "نام شهر", "شناسه"], city_rows)
write_csv("urban-areas.csv", ["استان", "شهرستان", "بخش", "شهر مادر", "کد منطقه", "نام منطقه شهری"], urban_rows)
settlement_rows = [sett_row(r) for r in all_sett]
settlement_rows.sort(key=lambda x: (x[0], x[1], x[2], x[3], x[4]))

write_csv("settlements-1404.csv",
          ["استان", "شهرستان", "بخش", "دهستان/والد", "کد آبادی", "نام آبادی"],
          settlement_rows)

# ---------------------------------------------------------------- آبادی‌ها به تفکیک استان
by_prov_sett = collections.defaultdict(list)
for r in settlement_rows:
    by_prov_sett[r[0]].append(r)

for p in provinces:
    items = by_prov_sett.get(p["Name"], [])
    safe = f"{p['Code']}-{p['Name']}".replace("/", "-")
    with open(os.path.join(SETT, f"{safe}.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["استان", "شهرستان", "بخش", "دهستان/والد", "کد آبادی", "نام آبادی"])
        w.writerows(items)

# ---------------------------------------------------------------- فصل‌های درخت (به تفکیک استان)
def fa(n):
    return f"{n:,}".replace(",", "٬")

tree_index = []
for p in provinces:
    pname = f"{p['Code']}-{p['Name']}".replace("/", "-")
    out = io.StringIO()
    w = out.write
    w(f"# استان {p['Name']} (کد {p['Code']})\n\n")
    w("> تولیدخودکار از دادهٔ رسمی فایل جغرافیایی مرکز آمار ایران، سال ۱۴۰۴. ")
    w("سطح «آبادی» در فایل‌های `data/settlements/` به تفکیک استان آمده است.\n\n")

    counties = ordered(children[p["Id"]])
    n_dist = n_deh = n_city = n_urban = n_sett = 0
    w("| شاخص | تعداد |\n|---|---|\n")

    body = io.StringIO()
    b = body.write
    for c in counties:
        b(f"\n### شهرستان {c['Name']} (کد {c['Code']})\n\n")
        districts = ordered(children[c["Id"]])
        if not districts:
            b("_بدون بخش ثبت‌شده در داده_\n")
        for d in districts:
            n_dist += 1
            b(f"\n#### بخش {d['Name']} (کد {d['Code']})\n\n")
            dehs, cities, urbs, setts = [], [], [], []
            for sub in ordered(children[d["Id"]]):
                t = sub["DivisionType"]
                if t == "4":
                    dehs.append(sub); n_deh += 1
                elif t == "5":
                    cities.append(sub); n_city += 1
                    for z in ordered(children[sub["Id"]]):
                        if z["DivisionType"] == "7":
                            urbs.append((sub, z)); n_urban += 1
                        elif z["DivisionType"] == "6":
                            setts.append(z); n_sett += 1
                elif t == "6":
                    setts.append(sub); n_sett += 1
            if dehs:
                b("\n**دهستان‌ها:**\n\n")
                for x in dehs:
                    cnt = len([v for v in children[x["Id"]] if v["DivisionType"] == "6"])
                    b(f"- {x['Name']} (کد {x['Code']}) — {fa(cnt)} آبادی\n")
            if cities:
                b("\n**شهرها:**\n\n")
                for x in cities:
                    ur = [z for z in children[x["Id"]] if z["DivisionType"] == "7"]
                    extra = f" — {len(ur)} منطقه شهری" if ur else ""
                    b(f"- {x['Name']} (کد {x['Code']}){extra}\n")
            if urbs:
                b("\n**مناطق شهری:**\n\n")
                for par, z in urbs:
                    b(f"- {z['Name']} (زیرمجموعهٔ {par['Name']})\n")
            if setts:
                b(f"\n**آبادی‌های وابسته مستقیم ({len(setts)}):** ")
                b("، ".join(x["Name"] for x in setts) + "\n")

    total_sett = len(by_prov_sett.get(p["Name"], []))
    # جدول شاخص‌ها را بعد از محاسبه می‌نویسیم
    header_tbl = f"| شاخص | تعداد |\n|---|---|\n| شهرستان | {len(counties)} |\n| بخش | {n_dist} |\n| دهستان | {n_deh} |\n| شهر | {n_city} |\n| منطقه شهری | {n_urban} |\n| آبادی | {total_sett} |\n\n"
    text = out.getvalue().replace("| شاخص | تعداد |\n|---|---|\n", header_tbl) + body.getvalue()
    with open(os.path.join(TREE, f"{pname}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    tree_index.append((p["Code"], p["Name"], len(counties), n_dist, n_deh, n_city, n_urban, total_sett))

# ---------------------------------------------------------------- جدول تجمیعی استان‌ها
with open(os.path.join(DATA, "province-summary.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["کد", "استان", "شهرستان", "بخش", "دهستان", "شهر", "منطقه شهری", "آبادی"])
    for r in tree_index:
        w.writerow(r)
    w.writerow(["", "ایران (جمع)", len(county_rows), len(district_rows), len(dehestan_rows),
                len(city_rows), len(urban_rows), len(settlement_rows)])

print("provinces", len(prov_rows))
print("counties", len(county_rows))
print("districts", len(district_rows))
print("dehestans", len(dehestan_rows))
print("cities", len(city_rows))
print("urban", len(urban_rows))
print("settlements", len(settlement_rows))
print("tree chapters", len(tree_index))
print("settlement files", len(os.listdir(SETT)))
