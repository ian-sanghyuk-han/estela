# -*- coding: utf-8 -*-
"""한국 식품접객업 인허가 — 다섯 갈래를 받아 칸으로 쪼갠다.

행정안전부가 지방자치단체 인허가를 모아 내는 파일이다. 식품위생법이 식품접객업을 여섯으로
나누므로 파일도 여섯인데, 우리는 다섯을 가져오고 위탁급식(구내식당)만 뺀다 — 영국에서
학교와 병원을, 프랑스에서 급식을 뺀 것과 같은 이유다.

세 가지를 조심해야 한다.

**폐업이 대부분이다.** 이 파일은 인허가 대장이라 문 닫은 집이 그대로 남아 있고, 표본에서
71%가 폐업이었다. `영업상태명`이 `영업/정상`인 것만 남긴다.

**좌표가 한국 전용이다.** `좌표정보(X/Y)`는 **EPSG:5174**(Korean 1985 중부원점)다.
성심당 본점으로 맞춰 보면 5174가 오차 13 m, 5181이 323 m, 2097이 271 m — 5174가 맞다.
아는 자리 하나로 맞춰 보기 전에는 좌표계를 믿지 않는다.

**업태가 면허에 적혀 있다.** `위생업태명`이 한식·일식·중국식·호프/통닭·경양식…으로 들어
있다. 이건 우리가 짐작한 것이 아니라 **면허에 적힌 사실**이라, 요리를 추측해서 붙이지
않는다는 원칙을 어기지 않고 한국의 갈래 칸을 채울 수 있다.

편의점과 출장조리는 뺀다. 앞의 것은 가게이지 밥 먹으러 가는 곳이 아니고(영국에서 마트를,
미국에서 convenience를 뺀 것과 같다), 뒤의 것은 찾아갈 자리가 없다.

준비: data.go.kr에서 파일 다섯 개를 받아 `.harvest/` 에 둔다.
Run: python tools/harvest_korea.py
"""
import collections, csv, io, json, math, os, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CACHE = os.path.join(REPO, ".harvest")
REG = os.path.join(os.path.dirname(REPO), "estela-data", "registry")
if not os.path.isdir(REG):                       # 자료 저장소가 없으면 앱 안에 쓴다
    REG = os.path.join(REPO, "data", "registry")

STEPS = [0.25, 0.1, 0.05, 0.02, 0.01]
TARGET = 520

# 파일 이름, 출처 아이디, 폴더, 라벨
SETS = [
    ("식품_일반음식점.csv",   "kr-food",   "kr/food",   "한국 일반음식점"),
    ("식품_휴게음식점.csv",   "kr-rest",   "kr/rest",   "한국 휴게음식점 (카페·분식)"),
    ("식품_제과점영업.csv",   "kr-bakery", "kr/bakery", "한국 제과점 (빵집)"),
    ("식품_단란주점영업.csv", "kr-danran", "kr/danran", "한국 단란주점"),
    ("식품_유흥주점영업.csv", "kr-yuheung","kr/yuheung","한국 유흥주점"),
]

# 위생업태명 → 화면에 쓸 갈래. 면허에 적힌 말을 옮길 뿐 새로 판단하지 않는다
KIND = {
    "한식": "한식", "일식": "일식", "중국식": "중식", "경양식": "경양식",
    "분식": "분식", "횟집": "횟집", "냉면집": "냉면", "뷔페식": "뷔페",
    "호프/통닭": "호프·통닭", "통닭(치킨)": "치킨", "식육(숯불구이)": "고기구이",
    "정종/대포집/소주방": "주점", "감성주점": "주점", "탕류(보신용)": "탕류",
    "김밥(도시락)": "김밥·도시락", "패스트푸드": "패스트푸드",
    "패밀리레스트랑": "패밀리레스토랑", "외국음식전문점(인도,태국등)": "외국음식",
    "까페": "카페", "커피숍": "커피", "다방": "다방", "라이브카페": "라이브카페",
    "전통찻집": "찻집", "떡카페": "떡카페", "키즈카페": "키즈카페",
    "아이스크림": "아이스크림", "과자점": "과자점", "제과점영업": "빵집",
    "푸드트럭": "푸드트럭", "일반조리판매": "조리판매",
    "단란주점": "단란주점", "유흥주점": "유흥주점",
    "기타": "", "기타 휴게음식점": "", "백화점": "", "철도역구내": "",
    "극장": "", "관광호텔": "", "유원지": "", "고속도로": "", "공항": "",
}
DROP = {"편의점", "출장조리"}


def rows_of(path):
    """한 파일에서 쓸 수 있는 줄만 뽑는다. 좌표는 뭉치로 변환해야 빠르다."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)
    out, buf = [], []
    seen = collections.Counter()

    def flush():
        if not buf:
            return
        xs = [b[1] for b in buf]
        ys = [b[2] for b in buf]
        los, las = tr.transform(xs, ys)
        for (rec, _, _), la, lo in zip(buf, las, los):
            if not (33.0 <= la <= 38.7 and 124.5 <= lo <= 132.0):
                seen["나라 밖"] += 1          # 좌표가 튄 것 — 한반도 밖은 버린다
                continue
            rec[1] = round(la, 5)
            rec[2] = round(lo, 5)
            out.append(rec)
        del buf[:]

    with io.open(path, encoding="cp949", errors="replace", newline="") as h:
        for r in csv.DictReader(h):
            seen["전체"] += 1
            if r.get("영업상태명") != "영업/정상":
                seen["폐업"] += 1
                continue
            biz = (r.get("위생업태명") or "").strip()
            if biz in DROP:
                seen["밥집 아님"] += 1
                continue
            nm = (r.get("사업장명") or "").strip()
            x = (r.get("좌표정보(X)") or "").strip()
            y = (r.get("좌표정보(Y)") or "").strip()
            if not nm:
                seen["이름 없음"] += 1
                continue
            if not x or not y:
                seen["좌표 없음"] += 1
                continue
            try:
                fx, fy = float(x), float(y)
            except ValueError:
                seen["좌표 이상"] += 1
                continue
            ad = (r.get("도로명주소") or r.get("지번주소") or "").strip()
            kind = KIND.get(biz, biz)
            out.append([nm, 0.0, 0.0, ad[:52], kind])
            buf.append((out[-1], fx, fy))
            if len(buf) >= 20000:
                flush()
        flush()
    return out, seen


def choose_step(fine):
    agg = None
    for st in STEPS:
        m = int(round(st / .01))
        agg = collections.Counter()
        for (yy, xx), n in fine.items():
            agg[(yy // m, xx // m)] += n
        v = list(agg.values())
        if not v:
            return st
        if sum(v) / len(v) <= TARGET:
            return st
    return STEPS[-1]


def write_cells(rows, folder, step):
    d = os.path.join(REG, *folder.split("/"))
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    cells = collections.defaultdict(list)
    for r in rows:
        cells[(int(math.floor(r[1] / step)), int(math.floor(r[2] / step)))].append(r)
    index, nbytes = {}, 0
    for (cy, cx), rs in cells.items():
        y0, x0 = round(cy * step, 6), round(cx * step, 6)
        legend, li, out = [], {}, []
        rs.sort(key=lambda r: r[0])
        for nm, la, lo, ad, k in rs:
            if k not in li:
                li[k] = len(legend)
                legend.append(k)
            row = [nm, int(round((la - y0) * 1e5)), int(round((lo - x0) * 1e5)), li[k]]
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
    return index, nbytes


SOURCE = ("행정안전부 지방행정 인허가 데이터 — 식품접객업 {name}. 영업 중인 곳만. "
          "좌표 EPSG:5174 → WGS84 변환. 업태는 면허의 위생업태명을 그대로 옮긴 것이다.")
LICENCE = "이용허락범위 제한 없음 — 행정안전부 / 공공데이터포털"


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    mpath = os.path.join(REG, "manifest.json")
    man = json.load(io.open(mpath, encoding="utf-8"))
    grand = gbytes = 0
    for fname, sid, folder, label in SETS:
        p = os.path.join(CACHE, fname)
        if not os.path.exists(p):
            print("없음: %s — 건너뜀" % fname)
            continue
        t = time.time()
        rows, seen = rows_of(p)
        fine = collections.Counter()
        for r in rows:
            fine[(int(math.floor(r[1] / .01)), int(math.floor(r[2] / .01)))] += 1
        step = choose_step(fine)
        index, nbytes = write_cells(rows, folder, step)
        man["sources"][sid] = {
            "label": label, "country": "South Korea", "folder": folder,
            "step": step, "gov": True,
            "source": SOURCE.format(name=label), "license": LICENCE,
            "lastVerified": time.strftime("%Y-%m-%d"),
            "total": len(rows), "cells": index}
        grand += len(rows); gbytes += nbytes
        print("%-28s %9s곳 · %.2f° · 칸 %5d · %6.1f MB · 평균 %3.0f KB · %.0f초"
              % (label, format(len(rows), ","), step, len(index),
                 nbytes / 1048576, nbytes / max(1, len(index)) / 1024, time.time() - t))
        print("    걸러낸 것: " + " · ".join("%s %s" % (k, format(v, ","))
              for k, v in seen.most_common()))
    json.dump(man, io.open(mpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("\n한국 %s곳 · %.0f MB" % (format(grand, ","), gbytes / 1048576))
    print("전체 %s곳 · 출처 %d"
          % (format(sum(v["total"] for v in man["sources"].values()), ","),
             len(man["sources"])))


if __name__ == "__main__":
    main()
