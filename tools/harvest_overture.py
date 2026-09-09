# -*- coding: utf-8 -*-
"""Overture에서 세계의 밥집을 받아 우리 칸으로 쪼갠다. 되감기가 된다.

This tool lives in the repository on purpose. The first version of it lived in a temp
folder, the folder was cleaned mid-run, and an hour of harvesting plus every script that
knew how to redo it went with it. The shipped data survived; the ability to fix it did not.

Two phases, either runnable alone:

**받기.** 648 tiles of ten degrees. Nine and a half million rows will not fit in memory at
once, and Overture's files are laid out geographically, so a tile predicate reads only the
row groups that overlap — ocean answers in a second. A tile already on disk is skipped, so
stopping costs nothing.

**쪼개기.** Grouped by country, because a grid that suits the English countryside is
useless in Bangkok: one 0.25° cell there came to 2.7 MB, which is what a single search
would have downloaded. Each country gets the coarsest grid whose cells still hold about
five hundred places, chosen by counting rather than by guessing.

Countries whose entire territory is already covered by a government register — Britain,
France, Denmark, Hong Kong — are skipped, so the same restaurant does not answer twice.
Where our coverage is partial, like the United States, Overture is kept and the duplicate
is resolved in the search instead, preferring the licence over the aggregation.

Run: python tools/harvest_overture.py [--pull] [--shard] [--top N] [--conf 0.2]
"""
import argparse, collections, io, json, math, os, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CACHE = os.path.join(REPO, ".harvest")            # git이 무시한다. 수십 GB가 될 수 있다
REG = os.path.join(os.path.dirname(REPO), "estela-data", "registry")
if not os.path.isdir(REG):                        # 자료 저장소가 없으면 앱 안에 쓴다
    REG = os.path.join(REPO, "data", "registry")
REL = "2026-08-19.0"
SRC = "s3://overturemaps-us-west-2/release/%s/theme=places/type=place/*.parquet" % REL

# 나라 전체를 덮는 정부 명부가 이미 있는 곳 — 겹쳐 싣지 않는다.
# 한국은 2026-09-09에 식품접객업 다섯 갈래 86만 곳이 들어와 이 무리에 합류했다
SKIP = {"GB", "FR", "DK", "HK", "KR"}
STEPS = [0.25, 0.1, 0.05, 0.02, 0.01]
TARGET = 520                                      # 칸 하나에 이만큼이면 30~60 KB다

KIND = {
    "restaurant": "레스토랑", "casual_eatery": "간이식당", "cafe": "카페",
    "coffee_shop": "커피", "bar": "바", "pub": "펍",
    "fast_food_restaurant": "패스트푸드", "food_truck_stand": "노점·푸드트럭",
    "bakery": "빵집", "dessert_shop": "디저트", "ice_cream_shop": "아이스크림",
    "food_court": "푸드코트", "brewery": "양조장", "winery": "와이너리",
    "distillery": "증류소", "lounge": "라운지", "smoothie_juice_bar": "주스·스무디",
    "non_alcoholic_beverage_venue": "음료", "alcoholic_beverage_venue": "주류",
    "buffet_restaurant": "뷔페", "steakhouse": "스테이크", "sushi_restaurant": "스시",
    "pizza_restaurant": "피자", "noodle_restaurant": "면요리", "food_and_drink": "",
}

CC = {
 "US": "United States", "JP": "Japan", "BR": "Brazil", "MX": "Mexico", "TH": "Thailand",
 "IT": "Italy", "ID": "Indonesia", "GB": "United Kingdom", "VN": "Vietnam", "IN": "India",
 "DE": "Germany", "FR": "France", "ES": "Spain", "TW": "Taiwan", "TR": "Turkey",
 "KR": "South Korea", "PH": "Philippines", "MY": "Malaysia", "CA": "Canada",
 "AU": "Australia", "CO": "Colombia", "GR": "Greece", "AR": "Argentina", "PL": "Poland",
 "RU": "Russia", "PE": "Peru", "PT": "Portugal", "NL": "Netherlands", "BE": "Belgium",
 "ZA": "South Africa", "CL": "Chile", "CZ": "Czechia", "SE": "Sweden", "AT": "Austria",
 "CH": "Switzerland", "EC": "Ecuador", "RO": "Romania", "UA": "Ukraine", "EG": "Egypt",
 "HK": "Hong Kong", "CN": "China", "HU": "Hungary", "SA": "Saudi Arabia",
 "SG": "Singapore", "BG": "Bulgaria", "DK": "Denmark", "NO": "Norway", "FI": "Finland",
 "IE": "Ireland", "NZ": "New Zealand", "IL": "Israel", "AE": "United Arab Emirates",
 "MA": "Morocco", "NG": "Nigeria", "KE": "Kenya", "PK": "Pakistan", "BD": "Bangladesh",
 "LK": "Sri Lanka", "NP": "Nepal", "KH": "Cambodia", "LA": "Laos", "MM": "Myanmar",
 "BN": "Brunei", "MN": "Mongolia", "KZ": "Kazakhstan", "UZ": "Uzbekistan",
 "GE": "Georgia", "AM": "Armenia", "AZ": "Azerbaijan", "RS": "Serbia", "HR": "Croatia",
 "SI": "Slovenia", "SK": "Slovakia", "LT": "Lithuania", "LV": "Latvia", "EE": "Estonia",
 "IS": "Iceland", "LU": "Luxembourg", "MT": "Malta", "CY": "Cyprus", "UY": "Uruguay",
 "PY": "Paraguay", "BO": "Bolivia", "VE": "Venezuela", "CR": "Costa Rica",
 "PA": "Panama", "GT": "Guatemala", "DO": "Dominican Republic", "CU": "Cuba",
 "JM": "Jamaica", "PR": "Puerto Rico", "TN": "Tunisia", "DZ": "Algeria", "GH": "Ghana",
 "TZ": "Tanzania", "ET": "Ethiopia", "UG": "Uganda", "SN": "Senegal",
 "CI": "Ivory Coast", "CM": "Cameroon", "ZW": "Zimbabwe", "ZM": "Zambia",
 "MU": "Mauritius", "QA": "Qatar", "KW": "Kuwait", "BH": "Bahrain", "OM": "Oman",
 "JO": "Jordan", "LB": "Lebanon", "IQ": "Iraq", "IR": "Iran", "AL": "Albania",
 "MK": "North Macedonia", "BA": "Bosnia and Herzegovina", "ME": "Montenegro",
 "MD": "Moldova", "BY": "Belarus", "ZZ": "어디인지 모를 곳",
}

Q = """
SELECT names.primary, round(bbox.ymin,5), round(bbox.xmin,5),
       addresses[1].freeform, basic_category, addresses[1].country, round(confidence,2)
FROM read_parquet('{src}')
WHERE bbox.xmin >= {w} AND bbox.xmin < {e}
  AND bbox.ymin >= {s} AND bbox.ymin < {n}
  AND taxonomy.hierarchy[1] = 'food_and_drink'
  AND names.primary IS NOT NULL
  AND confidence >= 0.2
"""


def tiles_dir():
    d = os.path.join(CACHE, "tiles")
    if not os.path.isdir(d):
        os.makedirs(d)
    return d


def pull():
    import duckdb
    d = tiles_dir()
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    c.execute("SET preserve_insertion_order=false; SET memory_limit='3GB';")
    tiles = [(x, y) for y in range(-90, 90, 10) for x in range(-180, 180, 10)]
    # 사람이 사는 위도부터. 극지방은 뒤로 미룬다
    tiles.sort(key=lambda t: (abs(t[1] + 5) > 60, abs(t[1] + 5)))
    t0, grand, done = time.time(), 0, 0
    for x, y in tiles:
        p = os.path.join(d, "%d_%d.json" % (y, x))
        done += 1
        if os.path.exists(p):
            try:
                grand += len(json.load(io.open(p, encoding="utf-8")))
                continue
            except Exception:
                pass                                  # 깨진 타일은 다시 받는다
        t = time.time()
        rows = c.execute(Q.format(src=SRC, w=x, e=x + 10, s=y, n=y + 10)).fetchall()
        out = [[(a or "").strip(), b, cc, (dd or "").strip()[:52], e or "", f or "", g]
               for a, b, cc, dd, e, f, g in rows if (a or "").strip()]
        json.dump(out, io.open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        grand += len(out)
        if out:
            print("  %4d,%4d %9s곳 %5.0f초  누적 %s · %d/%d · %.0f분"
                  % (y, x, format(len(out), ","), time.time() - t,
                     format(grand, ","), done, len(tiles), (time.time() - t0) / 60),
                  flush=True)
    print("\n받기 끝. %s곳 · %.0f분" % (format(grand, ","), (time.time() - t0) / 60))


def choose_step(fine):
    """가장 성긴 격자부터 재 본다. 평균이 TARGET 아래로 내려오면 그걸 쓴다."""
    agg = None
    for st in STEPS:
        m = int(round(st / .01))
        agg = collections.Counter()
        for (y, x), n in fine.items():
            agg[(y // m, x // m)] += n
        v = list(agg.values())
        if not v:
            return st, agg
        if sum(v) / len(v) <= TARGET:
            return st, agg
    return STEPS[-1], agg


def write_country(cc, step, conf):
    folder = "ov/" + cc.lower()
    d = os.path.join(REG, *folder.split("/"))
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    cells = collections.defaultdict(list)
    with io.open(os.path.join(CACHE, "bycc", cc + ".jsonl"), encoding="utf-8") as h:
        for line in h:
            n, la, lo, ad, cat = json.loads(line)
            cells[(int(math.floor(la / step)), int(math.floor(lo / step)))].append(
                (n, la, lo, ad, cat))
    index, nbytes, total = {}, 0, 0
    for (cy, cx), rows in cells.items():
        y0, x0 = round(cy * step, 6), round(cx * step, 6)
        legend, li, out = [], {}, []
        rows.sort(key=lambda r: r[0])
        for n, la, lo, ad, cat in rows:
            k = KIND.get(cat, (cat or "").replace("_", " "))
            if k not in li:
                li[k] = len(legend)
                legend.append(k)
            row = [n, int(round((la - y0) * 1e5)), int(round((lo - x0) * 1e5)), li[k]]
            if ad:
                row.append(ad)
            out.append(row)
        key = "%d_%d" % (cy, cx)
        p = os.path.join(d, key + ".json")
        json.dump({"o": [y0, x0], "k": legend, "p": out},
                  io.open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        index[key] = len(out)
        nbytes += os.path.getsize(p)
        total += len(out)
    return folder, index, total, nbytes


def shard(conf, top):
    bycc = os.path.join(CACHE, "bycc")
    if os.path.isdir(bycc):
        shutil.rmtree(bycc)
    os.makedirs(bycc)
    print("① 나라별로 흩는 중…")
    fh, tally, kept, dropped = {}, collections.defaultdict(collections.Counter), 0, 0
    files = sorted(os.listdir(tiles_dir()))
    for i, f in enumerate(files):
        try:
            rows = json.load(io.open(os.path.join(tiles_dir(), f), encoding="utf-8"))
        except Exception:
            continue
        for n, la, lo, ad, cat, cc, cf in rows:
            if (cf is not None and cf < conf) or (cc or "").upper() in SKIP:
                dropped += 1
                continue
            cc = (cc or "ZZ").upper()
            if cc not in fh:
                fh[cc] = io.open(os.path.join(bycc, cc + ".jsonl"), "w",
                                 encoding="utf-8", newline="\n")
            fh[cc].write(json.dumps([n, la, lo, ad, cat],
                                    ensure_ascii=False, separators=(",", ":")) + "\n")
            tally[cc][(int(math.floor(la / .01)), int(math.floor(lo / .01)))] += 1
            kept += 1
        if i % 80 == 0:
            print("   타일 %d/%d · %s곳" % (i, len(files), format(kept, ",")), flush=True)
    for h in fh.values():
        h.close()
    print("   남긴 것 %s · 버린 것 %s" % (format(kept, ","), format(dropped, ",")))

    mpath = os.path.join(REG, "manifest.json")
    man = json.load(io.open(mpath, encoding="utf-8"))
    man["version"] = 3
    for k in [k for k in man["sources"] if k.startswith("ov-")]:
        f = man["sources"][k].get("folder")
        if f and os.path.isdir(os.path.join(REG, *f.split("/"))):
            shutil.rmtree(os.path.join(REG, *f.split("/")))
        del man["sources"][k]
    for v in man["sources"].values():
        v["gov"] = True                     # 남은 것은 전부 정부 자료다

    src_note = ("Overture Maps Foundation places theme, release %s — food_and_drink "
                "taxonomy, confidence >= %.2f. Conflated from Meta, Microsoft, "
                "Foursquare, PinMeTo and others; contains no OpenStreetMap data."
                % (REL, conf))
    lic = "CDLA Permissive 2.0 / Apache 2.0 — Overture Maps Foundation"

    print("\n② 나라마다 격자를 골라 쓰는 중…")
    order = sorted(tally, key=lambda c: -sum(tally[c].values()))
    if top:
        order = order[:top]
    grand = gbytes = gcells = 0
    for cc in order:
        if sum(tally[cc].values()) < 40:
            continue
        step, _ = choose_step(tally[cc])
        folder, index, total, nbytes = write_country(cc, step, conf)
        man["sources"]["ov-" + cc.lower()] = {
            "label": CC.get(cc, cc) + " 식음업소", "country": CC.get(cc, cc),
            "folder": folder, "step": step, "gov": False,
            "source": src_note, "license": lic,
            "lastVerified": time.strftime("%Y-%m-%d"),
            "total": total, "cells": index}
        grand += total; gbytes += nbytes; gcells += len(index)
        if total > 20000:
            print("   %-3s %9s곳 · %.2f° · 칸 %5d · %6.1f MB · 평균 %4.0f KB"
                  % (cc, format(total, ","), step, len(index), nbytes / 1048576,
                     nbytes / max(1, len(index)) / 1024), flush=True)
    json.dump(man, io.open(mpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("\nOverture %s곳 · 나라 %d · 칸 %s · %.0f MB"
          % (format(grand, ","),
             len([k for k in man["sources"] if k.startswith("ov-")]),
             format(gcells, ","), gbytes / 1048576))
    print("manifest %.0f KB · 출처 %d · 전체 %s곳"
          % (os.path.getsize(mpath) / 1024, len(man["sources"]),
             format(sum(v["total"] for v in man["sources"].values()), ",")))


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--shard", action="store_true")
    ap.add_argument("--conf", type=float, default=0.2)
    ap.add_argument("--top", type=int, default=0, help="곳 수 많은 N개국만")
    a = ap.parse_args()
    if a.pull or not a.shard:
        pull()
    if a.shard or not a.pull:
        shard(a.conf, a.top)
