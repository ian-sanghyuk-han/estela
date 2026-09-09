# -*- coding: utf-8 -*-
"""정부 명부를 다시 받는다 — 나라마다 문이 다르다.

한국과 Overture 말고 나머지 열아홉 명부의 채취기는 임시 폴더가 지워질 때 같이
사라졌다. 자동 갱신을 말하려면 이것부터 있어야 한다. 이번에는 저장소 안에 둔다.

명부마다 받는 길이 다르므로 출처 하나에 함수 하나다. 공통은 세 가지뿐이다 —
**관할 구역 밖으로 튄 줄을 버리고**, 이름+좌표가 같은 줄을 하나로 접고, 칸으로 쪼갠다.

관할 구역 검사는 장식이 아니다. 처음 받았을 때 댈러스는 21.8%가 댈러스 밖(하와이·
알래스카까지)이었고, 뉴욕주는 경도 −778을 냈고, 새너제이는 좌표 한 쌍이 뒤집혀 터키로
갔다. **남의 지오코딩을 믿지 마라.**

위생 등급·점수·판정은 싣지 않는다. 우리가 평가하지 않는다는 원칙이고, 그 값들이
빠지면 자료도 가벼워진다.

Run: python tools/harvest_gov.py            (무엇이 있는지 보여 준다)
     python tools/harvest_gov.py fr-alim dk-smiley
     python tools/harvest_gov.py all
"""
import collections, csv, io, json, math, os, re, shutil, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CACHE = os.path.join(REPO, ".harvest")
REG = os.path.join(os.path.dirname(REPO), "estela-data", "registry")
if not os.path.isdir(REG):
    REG = os.path.join(REPO, "data", "registry")

# 괄호와 세미콜론이 든 이름표를 막는 서버가 있다. 보스턴은 그걸로 502를 뱉었고
# 나는 서버가 죽은 줄 알았다. 이름표는 짧게 둔다
UA = {"User-Agent": "estela/1.0"}
STEPS = [0.25, 0.1, 0.05, 0.02, 0.01]
TARGET = 520


# ─────────────────────────────────────────────────────────────── 공통

def get(url, params=None, timeout=180, headers=None, tries=3):
    import requests
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                             headers=dict(UA, **(headers or {})))
            if r.status_code == 200:
                return r
            last = "HTTP %d" % r.status_code
        except Exception as e:
            last = str(e)[:90]
        time.sleep(2 + 3 * i)
    raise RuntimeError("%s — %s" % (last, url[:90]))


def num(v):
    try:
        f = float(v)
        return f if f == f else None          # NaN 거르기
    except (TypeError, ValueError):
        return None


def inbox(la, lo, bx):
    return la is not None and lo is not None and \
        bx[0] <= la <= bx[2] and bx[1] <= lo <= bx[3]


def clean(rows, bbox, label):
    """관할 구역 밖을 버리고, 같은 가게를 접는다."""
    out, seen = [], set()
    drop = collections.Counter()
    for nm, la, lo, ad, kd in rows:
        nm = (nm or "").strip()
        if not nm:
            drop["이름 없음"] += 1
            continue
        la, lo = num(la), num(lo)
        if la is None or lo is None:
            drop["좌표 없음"] += 1
            continue
        if not inbox(la, lo, bbox):
            drop["관할 밖"] += 1
            continue
        k = (nm.lower(), round(la, 4), round(lo, 4))
        if k in seen:
            drop["같은 가게"] += 1
            continue
        seen.add(k)
        out.append([nm[:60], round(la, 5), round(lo, 5), (ad or "").strip()[:52],
                    (kd or "").strip()[:24]])
    if drop:
        print("    걸러낸 것: " + " · ".join("%s %s" % (k, format(v, ","))
              for k, v in drop.most_common()))
    return out


def choose_step(rows):
    fine = collections.Counter()
    for r in rows:
        fine[(int(math.floor(r[1] / .01)), int(math.floor(r[2] / .01)))] += 1
    for st in STEPS:
        m = int(round(st / .01))
        agg = collections.Counter()
        for (yy, xx), n in fine.items():
            agg[(yy // m, xx // m)] += n
        v = list(agg.values())
        if not v or sum(v) / len(v) <= TARGET:
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


def socrata(domain, ds, select=None, where=None, page=50000, cap=None):
    """Socrata 한 자료를 통째로 — 쪽을 넘기며. :id 순으로 넘겨야 빠지는 줄이 없다."""
    out, off = [], 0
    while True:
        p = {"$limit": page, "$offset": off, "$order": ":id"}
        if select:
            p["$select"] = select
        if where:
            p["$where"] = where
        j = get("https://%s/resource/%s.json" % (domain, ds), params=p).json()
        out.extend(j)
        if len(j) < page or (cap and len(out) >= cap):
            break
        off += page
        print("      %s개…" % format(len(out), ","), flush=True)
    return out


def pt(r, latk="latitude", lonk="longitude", objk=None):
    """Socrata 는 좌표를 두 칸에 넣기도 하고 점 객체에 넣기도 한다."""
    la, lo = num(r.get(latk)), num(r.get(lonk))
    if la is None and objk:
        g = r.get(objk) or {}
        c = (g.get("coordinates") if isinstance(g, dict) else None) or []
        if len(c) == 2:
            lo, la = num(c[0]), num(c[1])
        elif isinstance(g, dict):
            la, lo = num(g.get("latitude")), num(g.get("longitude"))
    return la, lo


# ─────────────────────────────────────────────────────────── 출처마다

def fr_alim(which):
    """Alim'confiance — 전국 한 장. 위생 판정(synthese_eval_sanit)은 싣지 않는다.

    가르는 칸은 활동 갈래(214가지나 된다)가 아니라 **type_activite**다. 이 칸이
    Restauration commerciale(식당) / Métier de bouche(빵집·정육점·생선가게) /
    Restauration collective(급식)를 이미 갈라 놓았다. 급식은 가져오지 않는다 —
    영국에서 학교와 병원을 뺀 것과 같은 이유다."""
    TYPE = ("Restauration commerciale" if which == "resto" else "Métier de bouche")
    # 쪽 넘기기(records)는 10,000줄에서 막힌다. 여긴 7만 줄이라 통째로 내보내는 문을 쓴다
    url = ("https://dgal.opendatasoft.com/api/explore/v2.1/catalog/"
           "datasets/export_alimconfiance/exports/csv")
    r = get(url, params={"delimiter": ";"}, timeout=900)
    txt = r.content.decode("utf-8-sig", "replace")
    rows = []
    for d in csv.DictReader(io.StringIO(txt), delimiter=";"):
        if (d.get("type_activite") or "").strip() != TYPE:
            continue
        g = (d.get("geores") or "").split(",")
        la = g[0].strip() if len(g) == 2 else None
        lo = g[1].strip() if len(g) == 2 else None
        ad = " ".join(x for x in [d.get("adresse_activite"), d.get("code_postal"),
                                  d.get("com_name")] if x)
        act = [a.strip() for a in
               (d.get("app_libelle_activite_etablissement") or "").split(",")
               if a.strip()]
        rows.append([d.get("app_libelle_etablissement"), la, lo, ad,
                     "레스토랑" if which == "resto" else (act[0] if act else "")])
    return rows, (41.0, -5.5, 51.5, 9.8), \
        ("DGAL Alim'confiance — %s. 위생 판정은 싣지 않는다." % TYPE), \
        "Licence Ouverte 2.0 — © DGAL / data.gouv.fr", "France"


def geocode_dk(addrs, workers=8):
    """덴마크 주소 → 좌표. DAWA(Danmarks Adressers Web API), 무료·열쇠 없음.

    한 번 물어본 주소는 `.harvest/dk_als.json`에 적어 둔다. 다음 갱신에서 새로 생긴
    가게만 물어보면 되므로, 두 번째부터는 몇 초로 끝난다."""
    import threading
    cpath = os.path.join(CACHE, "dk_geo.json")
    cache = {}
    if os.path.exists(cpath):
        try:
            cache = json.load(io.open(cpath, encoding="utf-8"))
        except Exception:
            cache = {}
    todo = [a for a in set(addrs) if a not in cache]
    print("    좌표 물어볼 주소 %s개 (이미 아는 것 %s개)"
          % (format(len(todo), ","), format(len(cache), ",")), flush=True)
    lock, done = threading.Lock(), [0]

    def work(chunk):
        import requests
        s = requests.Session()
        s.headers.update(UA)
        for a in chunk:
            xy = None
            try:
                r = s.get("https://api.dataforsyningen.dk/adresser",
                          params={"q": a, "per_side": 1, "struktur": "mini"},
                          timeout=30)
                j = r.json()
                if j:
                    xy = [j[0].get("y"), j[0].get("x")]     # 위도, 경도
            except Exception:
                xy = None
            with lock:
                cache[a] = xy
                done[0] += 1
                if done[0] % 2000 == 0:
                    print("      %s/%s" % (format(done[0], ","),
                                           format(len(todo), ",")), flush=True)
    ts = []
    for i in range(workers):
        t = threading.Thread(target=work, args=(todo[i::workers],))
        t.start()
        ts.append(t)
    for t in ts:
        t.join()
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)
    json.dump(cache, io.open(cpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    return cache


def dk_smiley():
    """Fødevarestyrelsen Smiley — 스마일리 등급은 싣지 않는다.

    예전 파일에는 Geo_Lat/Geo_Lng가 있었는데 지금은 **좌표가 통째로 빠졌고** 칸 이름도
    다 바뀌었다. 그래서 덴마크 정부의 주소 API로 좌표를 붙인다 — 홍콩에서 배운 것과
    같다. 명부에 좌표가 없다고 끝난 게 아니라, 같은 정부가 주소 조회를 열어 두었는지
    먼저 본다."""
    import xml.etree.ElementTree as ET
    KEEP = {"Serveringsvirksomhed - Restauranter m.v.",
            "Serveringsvirksomhed - Uden behandling",
            "Specialforretning - Bager m.v."}
    r = get("https://pub.fvst.dk/publikationer/Smileydata.xml", timeout=900)
    root = ET.fromstring(r.content)
    raw = []
    for e in root:
        g = {c.tag: (c.text or "").strip() for c in e}
        br = g.get("FVST_branche", "")
        if br not in KEEP:
            continue
        nm = g.get("Virksomhed")
        ad = ", ".join(x for x in [g.get("Adresse"),
                                   " ".join(y for y in [g.get("Postnummer"),
                                                        g.get("By")] if y)] if x)
        if not nm or not ad:
            continue
        raw.append([nm, ad, "빵집" if "Bager" in br else "레스토랑"])
    cache = geocode_dk([a for _, a, _ in raw])
    rows = []
    for nm, ad, kd in raw:
        xy = cache.get(ad)
        if not xy:
            continue
        rows.append([nm, xy[0], xy[1], ad, kd])
    return rows, (54.4, 7.8, 57.9, 15.3), \
        ("Fødevarestyrelsen Smiley — Serveringsvirksomhed (Restauranter, "
         "Uden behandling) 및 Bager. 좌표는 명부에 없어 DAWA 주소 API로 붙였다. "
         "스마일리 등급은 싣지 않는다."), \
        "Danish public-sector open data terms — © Fødevarestyrelsen", "Denmark"


def uk_fhrs():
    """FSA 위생 등급 제도 — 지자체별 파일. 등급은 싣지 않는다."""
    import xml.etree.ElementTree as ET
    KEEP = {"Restaurant/Cafe/Canteen", "Pub/bar/nightclub", "Takeaway/sandwich shop"}
    auth = get("https://api.ratings.food.gov.uk/Authorities/basic",
               headers={"x-api-version": "2", "Accept": "application/json"}).json()
    ids = [a["LocalAuthorityIdCode"] for a in auth.get("authorities", [])]
    print("    지자체 %d곳" % len(ids), flush=True)
    rows = []
    for i, code in enumerate(ids):
        try:
            r = get("https://ratings.food.gov.uk/api/open-data-files/FHRS%sen-GB.xml"
                    % code, timeout=180, tries=2)
            root = ET.fromstring(r.content)
        except Exception:
            continue
        for e in root.iter("EstablishmentDetail"):
            g = {c.tag: c for c in e}
            bt = (g["BusinessType"].text or "") if "BusinessType" in g else ""
            if bt not in KEEP:
                continue
            geo = g.get("Geocode")
            la = lo = None
            if geo is not None:
                for c in geo:
                    if c.tag == "Latitude":
                        la = c.text
                    elif c.tag == "Longitude":
                        lo = c.text
            ad = " ".join((g[k].text or "") for k in
                          ("AddressLine1", "AddressLine2", "AddressLine3",
                           "AddressLine4", "PostCode") if k in g).strip()
            nm = (g["BusinessName"].text or "") if "BusinessName" in g else ""
            rows.append([nm, la, lo, re.sub(r"\s+", " ", ad), bt])
        if (i + 1) % 60 == 0:
            print("      %d/%d · %s곳" % (i + 1, len(ids), format(len(rows), ",")),
                  flush=True)
    return rows, (49.8, -8.7, 61.0, 1.9), \
        ("Food Standards Agency, Food Hygiene Rating Scheme — "
         "Restaurant/Cafe/Canteen, Pub/bar/nightclub, Takeaway/sandwich shop. "
         "위생 등급은 싣지 않는다."), \
        "Open Government Licence v3.0 — © Crown copyright", "United Kingdom"


def geocode(addrs, ask, cache_name, workers=8):
    """주소 뭉치에 좌표를 붙인다. 한 번 물어본 것은 적어 두고 다시 묻지 않는다.

    명부에 좌표가 없다고 끝이 아니다 — 같은 정부가 주소 조회를 열어 두었는지 먼저 본다.
    홍콩(ALS)과 덴마크(DAWA)가 그렇다. 이걸 확인하기 전에 나라를 포기하지 마라."""
    import threading
    cpath = os.path.join(CACHE, cache_name)
    cache = {}
    if os.path.exists(cpath):
        try:
            cache = json.load(io.open(cpath, encoding="utf-8"))
        except Exception:
            cache = {}
    todo = [a for a in set(addrs) if a and a not in cache]
    print("    좌표 물어볼 주소 %s개 (이미 아는 것 %s개)"
          % (format(len(todo), ","), format(len(cache), ",")), flush=True)
    lock, done = threading.Lock(), [0]

    def work(chunk):
        import requests
        s = requests.Session()
        s.headers.update(dict(UA, Accept="application/json"))
        for a in chunk:
            try:
                xy = ask(s, a)
            except Exception:
                xy = None
            with lock:
                cache[a] = xy
                done[0] += 1
                if done[0] % 2000 == 0:
                    print("      %s/%s" % (format(done[0], ","),
                                           format(len(todo), ",")), flush=True)
    ts = []
    for i in range(workers):
        t = threading.Thread(target=work, args=(todo[i::workers],))
        t.start()
        ts.append(t)
    for t in ts:
        t.join()
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)
    json.dump(cache, io.open(cpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    return cache


def hk_fehd():
    """FEHD 식당 면허 — 이름이 «간판»이라 다른 나라 명부보다 낫다.

    보통 명부는 면허를 쥔 법인 이름을 싣는데, 여기 SS 칸은 **문 위에 실제로 걸린
    간판**이다. 대신 좌표가 통째로 없다. 홍콩 정부가 따로 여는 주소 조회(ALS)로 붙인다."""
    import xml.etree.ElementTree as ET
    r = get("https://www.fehd.gov.hk/english/licensing/license/text/"
            "LP_Restaurants_EN.XML", timeout=600)
    root = ET.fromstring(r.content)
    raw = []
    for e in root.iter("LP"):
        g = {c.tag: (c.text or "").strip() for c in e}
        nm, ad = g.get("SS"), g.get("ADR")
        if not nm or not ad:
            continue
        raw.append([nm, ad, g.get("TYPE", ""), g.get("DIST", "")])

    def ask(s, a):
        j = s.get("https://www.als.gov.hk/lookup",
                  params={"q": a, "n": 1}, timeout=30).json()
        sa = j.get("SuggestedAddress") or []
        if not sa:
            return None
        gi = ((sa[0].get("Address") or {}).get("PremisesAddress") or {}) \
            .get("GeospatialInformation") or {}
        la, lo = num(gi.get("Latitude")), num(gi.get("Longitude"))
        return [la, lo] if la is not None else None

    # 32-40 Wellington Street 같은 범위 주소는 한 번에 안 잡힌다.
    # 뒤에서 세 토막만 남겨 다시 물으면 대개 걸린다
    cache = geocode([a for _, a, _, _ in raw], ask, "hk_als.json")
    retry = [a for _, a, _, _ in raw if not cache.get(a)]
    short = {a: ", ".join(a.split(",")[-3:]).strip() for a in retry}
    if short:
        c2 = geocode(list(short.values()), ask, "hk_als.json")
        for a, s in short.items():
            if c2.get(s):
                cache[a] = c2[s]
    rows = []
    for nm, ad, tp, dist in raw:
        xy = cache.get(ad)
        if not xy:
            continue
        rows.append([nm, xy[0], xy[1], joinp(ad, dist), tp])
    return rows, (22.13, 113.80, 22.58, 114.45), \
        ("FEHD restaurant licences (General, Light Refreshment, Marine), 일일 XML. "
         "이름은 문에 걸린 간판(SS)이다. 좌표는 홍콩 정부 주소 조회(ALS)로 붙였다."), \
        "Open data — © Food and Environmental Hygiene Department, HKSAR", "Hong Kong"


def geocode_us(addrs, chunk=4000, workers=4):
    """미국 주소 → 좌표. 인구조사국 뭉치 조회 — 무료, 열쇠 없음, 한 번에 1만 줄.

    펜실베이니아 명부에는 좌표 칸이 아예 없다. 주와 도시가 제각각인 나라라 이런 일이
    흔하고, 그럴 때 쓰라고 연방이 열어 둔 문이다."""
    import threading
    cpath = os.path.join(CACHE, "us_census_geo.json")
    cache = {}
    if os.path.exists(cpath):
        try:
            cache = json.load(io.open(cpath, encoding="utf-8"))
        except Exception:
            cache = {}
    todo = sorted(a for a in set(addrs) if a and a not in cache)
    print("    좌표 물어볼 주소 %s개 (이미 아는 것 %s개)"
          % (format(len(todo), ","), format(len(cache), ",")), flush=True)
    parts = [todo[i:i + chunk] for i in range(0, len(todo), chunk)]
    lock, done = threading.Lock(), [0]

    def work(myparts):
        import requests
        s = requests.Session()
        s.headers.update(UA)
        for pa in myparts:
            buf = io.StringIO()
            w = csv.writer(buf)
            for i, a in enumerate(pa):
                bits = [x.strip() for x in a.split("|")]
                while len(bits) < 4:
                    bits.append("")
                w.writerow([i] + bits[:4])
            try:
                r = s.post("https://geocoding.geo.census.gov/geocoder/locations/"
                           "addressbatch",
                           files={"addressFile": ("a.csv", buf.getvalue(), "text/csv")},
                           data={"benchmark": "Public_AR_Current"}, timeout=900)
                got = {}
                for row in csv.reader(io.StringIO(r.text)):
                    if len(row) >= 6 and row[2] == "Match":
                        lo, la = row[5].split(",")
                        got[int(row[0])] = [num(la), num(lo)]
            except Exception:
                got = {}
            with lock:
                for i, a in enumerate(pa):
                    cache[a] = got.get(i)
                done[0] += 1
                print("      뭉치 %d/%d" % (done[0], len(parts)), flush=True)
    ts = []
    for i in range(workers):
        t = threading.Thread(target=work, args=(parts[i::workers],))
        t.start()
        ts.append(t)
    for t in ts:
        t.join()
    if not os.path.isdir(CACHE):
        os.makedirs(CACHE)
    json.dump(cache, io.open(cpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    return cache


def us_pa():
    """펜실베이니아 농무부 — 좌표 칸이 없어 인구조사국에 물어 붙인다."""
    got = socrata("data.pa.gov", "etb6-jzdg")
    raw = []
    for r in got:
        if (r.get("active_indicator") or "").lower() != "yes":
            continue
        # 체스터 카운티는 «ChesterCountyFood»로 따로 적힌다. «Food»만 보다가
        # 9,359줄을 통째로 놓쳤다
        if "food" not in (r.get("program_group_type") or "").lower():
            continue
        nm = r.get("public_facility_name") or r.get("organization_name")
        ad = r.get("address")
        if not nm or not ad:
            continue
        # 인구조사국은 «09th»를 못 읽는다. 앞의 0을 떼면 대개 걸린다
        ad = re.sub(r"\b0(\d)(st|nd|rd|th)\b", r"\1\2", ad, flags=re.I)
        key = "|".join([ad, r.get("city") or "", "PA", r.get("zip_code") or ""])
        raw.append([nm, key, joinp(ad, r.get("city"), r.get("zip_code")), ad,
                    r.get("city") or "", r.get("zip_code") or ""])
    cache = geocode_us([k for _, k, _, _, _, _ in raw])
    # 못 찾은 주소는 호수·동·건물 이름을 떼고 다시 물어본다. 인구조사국은
    # «123 MAIN ST STE 4»를 못 읽지만 «123 MAIN ST»는 읽는다
    again = {}
    for _, key, _, ad, city, zp in raw:
        if cache.get(key):
            continue
        s = re.split(r"\b(?:ste|suite|apt|unit|rm|room|fl|floor|bldg|#)\b",
                     ad, 1, flags=re.I)[0].strip(" ,-")
        s = re.sub(r"\s+", " ", s)
        if s and s != ad:
            again[key] = "|".join([s, city, "PA", zp])
    if again:
        c2 = geocode_us(list(set(again.values())))
        for key, s in again.items():
            if c2.get(s):
                cache[key] = c2[s]
    rows = []
    for nm, key, ad, _, _, _ in raw:
        xy = cache.get(key)
        if not xy or xy[0] is None:
            continue
        rows.append([nm, xy[0], xy[1], ad, ""])
    return rows, (39.6, -80.6, 42.4, -74.6), \
        ("Pennsylvania Dept. of Agriculture — Public Food Inspections, 영업 중인 "
         "곳만. 명부에 좌표가 없어 미국 인구조사국 주소 조회로 붙였다."), \
        "Commonwealth of Pennsylvania open data", "United States"


def us_boston():
    """보스턴 식품업소 면허 — 유효한 면허만. 식료품점(Retail Food)은 뺀다."""
    # 보스턴 CKAN은 502를 자주 뱉는다. 문이 닫힌 게 아니라 숨을 고르는 것이라
    # 여러 번 두드리면 열린다
    pk = get("https://data.boston.gov/api/3/action/package_show",
             params={"id": "food-establishment-inspections"},
             headers={"Accept": "application/json"}, tries=8).json()["result"]
    url = next((x["url"] for x in pk["resources"]
                if (x.get("format") or "").upper() == "CSV"), None)
    if not url:
        raise RuntimeError("보스턴 CSV를 못 찾았다")
    txt = get(url, timeout=900).content.decode("utf-8-sig", "replace")
    rows = []
    for d in csv.DictReader(io.StringIO(txt)):
        if (d.get("licstatus") or "").strip().lower() != "active":
            continue
        # «Eating & Drinking»과 «Eating & Drinking w/ Take Out»은 다른 면허 갈래로
        # 적히는데 둘 다 밥 먹으러 가는 곳이다. 앞의 것만 보다가 1,367곳을 놓쳤다.
        # 식료품점(Retail Food)과 푸드트럭(Mobile)은 뺀다
        if not (d.get("descript") or "").strip().startswith("Eating & Drinking"):
            continue
        nm = (d.get("businessname") or d.get("dbaname") or "").strip()
        loc = (d.get("location") or "").strip("() ").split(",")
        la = loc[0] if len(loc) == 2 else None
        lo = loc[1] if len(loc) == 2 else None
        rows.append([nm, la, lo, joinp(d.get("address"), d.get("city"),
                                       d.get("zip")), ""])
    return rows, (42.22, -71.20, 42.40, -70.92), \
        ("City of Boston food establishment licences, 유효한 면허(Active)의 "
         "«Eating & Drinking»만. 식료품점은 뺀다. 점검 결과와 위반 내역은 싣지 않는다."), \
        "City of Boston Open Data", "United States"


def ca_toronto():
    """토론토 DineSafe — 업소 하나로 접는다. 업종 칸이 없어 식료품점이 섞인다."""
    pk = get("https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/"
             "package_show", params={"id": "dinesafe"}).json()["result"]
    url = None
    for res in pk["resources"]:
        if (res.get("format") or "").upper() == "CSV" and \
                (res.get("name") or "").lower().startswith("dinesafe"):
            url = res["url"]
            break
    if not url:
        raise RuntimeError("DineSafe CSV를 못 찾았다")
    txt = get(url, timeout=600).content.decode("utf-8-sig", "replace")
    rows = []
    for d in csv.DictReader(io.StringIO(txt)):
        k = {(a or "").strip().lower(): b for a, b in d.items()}
        nm = k.get("estname") or k.get("establishment name")
        if not nm:
            continue
        rows.append([nm, k.get("latitude"), k.get("longitude"),
                     k.get("address") or "", ""])
    return rows, (43.55, -79.70, 43.90, -79.10), \
        ("City of Toronto DineSafe, 업소 하나로 접었다. 점검 결과와 위반 내역은 "
         "싣지 않는다."), \
        "Open Government Licence – Toronto", "Canada"


def au_melbourne():
    """멜버른 시 사업체 총조사 — 면허 대장이 아니다. 최신 연도만.

    호주는 주와 지방의회마다 따로 등록해서 전국 명부가 없다. 시가 내는 총조사가
    그나마 가장 가까운 것이고, 그래서 멜버른 도심과 인접 구역뿐이다."""
    base = ("https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/"
            "business-establishments-with-address-and-industry-classification")
    meta = get(base + "/records", params={"limit": 1}).json()
    txt = get(base + "/exports/csv", params={"delimiter": ";"}, timeout=900) \
        .content.decode("utf-8-sig", "replace")
    d0 = list(csv.DictReader(io.StringIO(txt), delimiter=";"))
    yr = max((r.get("census_year") or "") for r in d0)
    KEEP = re.compile(r"caf|restaur|takeaway|food|bakery|pub|tavern|bar", re.I)
    rows = []
    for r in d0:
        if (r.get("census_year") or "") != yr:
            continue
        ind = r.get("industry_anzsic4_description") or \
            r.get("industry_anzsic_4_description") or ""
        if not KEEP.search(ind):
            continue
        g = (r.get("location") or r.get("geo_point_2d") or "").split(",")
        la = g[0].strip() if len(g) == 2 else r.get("latitude")
        lo = g[1].strip() if len(g) == 2 else r.get("longitude")
        ad = joinp(r.get("street_address"), r.get("clue_small_area"))
        rows.append([r.get("trading_name") or r.get("business_address"),
                     la, lo, ad, ind[:24]])
    return rows, (-38.00, 144.75, -37.70, 145.15), \
        ("City of Melbourne business census, 최신 연도(%s)만. 면허 대장이 아니라 "
         "도심과 인접 구역에 한정된다 — 호주는 지방의회마다 따로 등록해서 전국 "
         "명부가 없다." % yr), \
        "Creative Commons Attribution 4.0 — City of Melbourne", "Australia"


# ────────────────────────────────────────────── 미국 — 연방 명부가 없다

def us_source(cfg):
    """미국 도시·주 명부. 대개 Socrata이고, 칸 이름만 도시마다 다르다.

    미국에는 전국 명부가 없다. 도시와 카운티가 위생 점검 자료를 내는데, 그게 사실상
    그 도시의 식당 명부다. 점검 결과·점수·위반 내역은 싣지 않는다 — 우리가 평가하지
    않는다는 원칙이고, 그것들이 자료의 열에 아홉이다.

    **좌표는 반드시 관할 구역 안인지 본다.** 처음 받았을 때 댈러스는 21.8%가 시 밖
    (하와이·알래스카까지)이었다."""
    rows = []
    for ds in cfg["ds"]:
        got = socrata(cfg["domain"], ds)
        print("      %s · %s줄" % (ds, format(len(got), ",")), flush=True)
        for r in got:
            if cfg.get("keep") and not cfg["keep"](r):
                continue
            la, lo = pt(r, cfg.get("lat", "latitude"), cfg.get("lon", "longitude"),
                        cfg.get("pt"))
            rows.append([cfg["name"](r), la, lo, cfg.get("addr", lambda x: "")(r),
                         cfg.get("kind", lambda x: "")(r)])
    return rows, cfg["bbox"], cfg["source"], cfg["license"], "United States"


def joinp(*parts):
    return " ".join(str(p) for p in parts if p).strip()


NOT_FOOD = re.compile(r"grocer|convenien|market|liquor|pharmac|school|hospital|"
                      r"nursing|daycare|child care|warehouse|mobile|commissary|"
                      r"vending|caterer|wholesale", re.I)

US = {
 "us-nyc": dict(domain="data.cityofnewyork.us", ds=["43nn-pn8j"],
    bbox=(40.45, -74.30, 41.00, -73.65),
    name=lambda r: r.get("dba") or "",
    addr=lambda r: joinp(r.get("building"), r.get("street"), r.get("zipcode")),
    kind=lambda r: r.get("cuisine_description") or "",
    source=("NYC DOHMH restaurant inspection results, one row per CAMIS permit. "
            "점수와 등급은 싣지 않는다. 요리 갈래는 사실이므로 남긴다."),
    license="NYC Open Data — public domain"),

 "us-chicago": dict(domain="data.cityofchicago.org", ds=["4ijn-s7e5"],
    bbox=(41.60, -88.00, 42.10, -87.45),
    keep=lambda r: re.search(r"restaurant|bakery|tavern|coffee",
                             r.get("facility_type") or "", re.I),
    name=lambda r: r.get("aka_name") or r.get("dba_name") or "",
    addr=lambda r: joinp(r.get("address"), r.get("zip")),
    kind=lambda r: r.get("facility_type") or "",
    source=("City of Chicago food inspections, restaurant/bakery/tavern/coffee shop. "
            "쓰는 이름(aka_name)을 등록 이름보다 앞세운다. 점수와 판정은 싣지 않는다."),
    license="City of Chicago Open Data — public domain"),

 "us-nystate": dict(domain="health.data.ny.gov", ds=["cnih-y5dw"],
    bbox=(40.4, -79.9, 45.1, -71.8), pt="location1",
    keep=lambda r: not NOT_FOOD.search(r.get("description") or ""),
    name=lambda r: r.get("facility") or "",
    addr=lambda r: joinp(r.get("address"), r.get("city")),
    kind=lambda r: (r.get("description") or "").replace(
        "Food Service Establishment - ", ""),
    source="NY State DOH — Food Service Establishment: Last Inspection.",
    license="New York State open data"),

 "us-sanjose": dict(domain="data.sccgov.org", ds=["vuw7-jmjk"],
    bbox=(36.85, -122.25, 37.55, -121.20),
    keep=lambda r: not NOT_FOOD.search(r.get("name") or ""),
    name=lambda r: r.get("name") or "",
    addr=lambda r: joinp(r.get("address"), r.get("city"), r.get("postal_code")),
    source=("Santa Clara County DEH — food business list. 좌표 한 쌍이 뒤집혀 "
            "터키로 간 적이 있어 관할 구역 밖은 버린다."),
    license="County of Santa Clara open data"),

 "us-dallas": dict(domain="www.dallasopendata.com", ds=["dri5-wcct"],
    bbox=(32.55, -97.05, 33.10, -96.40), pt="lat_long",
    name=lambda r: r.get("program_identifier") or "",
    addr=lambda r: joinp(r.get("site_address"), r.get("zip")),
    source=("City of Dallas — Restaurant and Food Establishment Inspections. "
            "처음 받았을 때 21.8%가 댈러스 밖이었다 — 관할 구역 밖은 버린다."),
    license="City of Dallas open data"),

 "us-cincinnati": dict(domain="data.cincinnati-oh.gov", ds=["rg6p-b3h3"],
    bbox=(39.00, -84.80, 39.35, -84.20),
    keep=lambda r: (r.get("license_status") or "").lower() != "closed",
    name=lambda r: r.get("business_name") or "",
    addr=lambda r: joinp(r.get("address"), r.get("postal_code")),
    source="City of Cincinnati — Food Safety Program. 위반 내역은 싣지 않는다.",
    license="City of Cincinnati open data"),

 "us-montgomery": dict(domain="data.montgomerycountymd.gov", ds=["5pue-gfbe"],
    bbox=(38.90, -77.60, 39.40, -76.85),
    keep=lambda r: not NOT_FOOD.search(r.get("category") or r.get("type") or ""),
    name=lambda r: r.get("name") or "",
    addr=lambda r: joinp(r.get("address1"), r.get("city"), r.get("zip")),
    kind=lambda r: r.get("category") or "",
    source="Montgomery County MD — Food Inspection.",
    license="Montgomery County open data"),

 "us-kcmo": dict(domain="data.kcmo.org", ds=["sz9c-c5ux"],
    bbox=(38.80, -94.85, 39.40, -94.30), pt="location_1",
    keep=lambda r: (r.get("business_status") or "").lower() == "open"
                   and not NOT_FOOD.search(r.get("facility_type") or ""),
    name=lambda r: r.get("establishment_name") or r.get("facility_name") or "",
    addr=lambda r: joinp(r.get("facility_address"), r.get("facility_city"),
                         r.get("facility_zip")),
    kind=lambda r: r.get("facility_type") or "",
    source="Kansas City MO — food permits, 영업 중인 곳만.",
    license="City of Kansas City open data"),

 "us-cambridge": dict(domain="data.cambridgema.gov", ds=["iect-ma2e"],
    bbox=(42.33, -71.20, 42.43, -71.03),
    name=lambda r: r.get("dba") or r.get("business_name") or "",
    addr=lambda r: r.get("full_address") or "",
    kind=lambda r: r.get("food_est_permit_type") or r.get("permit_type") or "",
    source="City of Cambridge MA — Food Establishment Permits.",
    license="City of Cambridge open data"),

 "us-boulder": dict(domain="data.colorado.gov", ds=["6ytb-f2cq"],
    bbox=(39.85, -105.75, 40.30, -104.95), pt="location",
    name=lambda r: r.get("name") or "",
    addr=lambda r: joinp(r.get("address"), r.get("b1_situs_city"),
                         r.get("b1_situs_zip")),
    source=("Boulder County CO — Restaurant Inspections (2025년부터). 2013–2025년 "
            "묶음은 문 닫은 곳을 그대로 안고 있고 칸 이름도 달라 쓰지 않는다."),
    license="Colorado open data"),
}


# ─────────────────────────────────────────────────────────── 굴리는 곳

SETS = {
    "fr-alim":   dict(fn=lambda: fr_alim("resto"),  folder="fr-a",
                      label="프랑스 레스토랑 (Alim'confiance)"),
    "fr-bouche": dict(fn=lambda: fr_alim("bouche"), folder="fr-b",
                      label="프랑스 식품 소매 (Alim'confiance)"),
    "dk-smiley": dict(fn=dk_smiley, folder="dk",
                      label="덴마크 요식업 (Smiley)"),
    "uk-fhrs":   dict(fn=uk_fhrs,   folder="uk",
                      label="영국 식품위생 등급 명부"),
    "hk-fehd":   dict(fn=hk_fehd,   folder="hk",
                      label="홍콩 식당 면허"),
    "ca-toronto": dict(fn=ca_toronto, folder="ca/tor",
                       label="토론토 식품업소 (DineSafe)"),
    "au-melbourne": dict(fn=au_melbourne, folder="au/mel",
                         label="멜버른 요식업 (시 총조사)"),
    "us-pa":     dict(fn=us_pa,     folder="us/pa",
                      label="펜실베이니아 식품업소"),
    "us-boston": dict(fn=us_boston, folder="us/bos",
                      label="보스턴 식음업소"),
}
US_LABEL = {
    "us-nyc": ("뉴욕시 식당", "us/nyc"), "us-chicago": ("시카고 식당", "us/chi"),
    "us-nystate": ("뉴욕주 식품접객업", "us/nys"),
    "us-sanjose": ("샌타클래라 카운티 식품업소", "us/scc"),
    "us-dallas": ("댈러스 식당", "us/dal"),
    "us-cincinnati": ("신시내티 식품업소", "us/cin"),
    "us-montgomery": ("몽고메리 카운티 식품업소", "us/mtg"),
    "us-kcmo": ("캔자스시티 식품업소", "us/kc"),
    "us-cambridge": ("케임브리지 MA 식품업소", "us/cam"),
    "us-boulder": ("볼더 카운티 식당", "us/bld"),
}
for _sid, _cfg in US.items():
    _lab, _fold = US_LABEL[_sid]
    SETS[_sid] = dict(fn=(lambda c=_cfg: us_source(c)), folder=_fold, label=_lab)


def run(sid, before=0, force=False):
    cfg = SETS[sid]
    t = time.time()
    print("%s — 받는 중" % sid, flush=True)
    rows, bbox, source, licence, country = cfg["fn"]()
    print("    받은 줄 %s" % format(len(rows), ","), flush=True)
    rows = clean(rows, bbox, cfg["label"])
    if not rows:
        print("    아무것도 남지 않았다 — 건너뜀")
        return None
    # 자동 갱신은 사람이 안 보는 사이에 돈다. 원본이 바뀌거나 문이 반쯤 닫혀서
    # 절반만 받아 왔을 때 멀쩡한 사본을 그걸로 덮으면 조용히 자료를 잃는다.
    # 크게 줄었으면 멈추고 사람에게 묻는다
    if before and len(rows) < before * 0.6 and not force:
        print("    멈춤: 예전 %s곳 → 이번 %s곳 (60%% 아래). 원본을 확인하고 "
              "정말 맞으면 --force" % (format(before, ","), format(len(rows), ",")))
        return None
    step = choose_step(rows)
    index, nbytes = write_cells(rows, cfg["folder"], step)
    print("    %s곳 · %.2f° · 칸 %d · %.1f MB · %.0f초"
          % (format(len(rows), ","), step, len(index), nbytes / 1048576,
             time.time() - t), flush=True)
    return {"label": cfg["label"], "country": country, "folder": cfg["folder"],
            "step": step, "gov": True, "source": source, "license": licence,
            "lastVerified": time.strftime("%Y-%m-%d"),
            "total": len(rows), "cells": index}


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    want = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv
    if not want:
        print(__doc__)
        print("받을 수 있는 것: " + " ".join(sorted(SETS)))
        return
    if want == ["all"]:
        want = sorted(SETS)
    mpath = os.path.join(REG, "manifest.json")
    man = json.load(io.open(mpath, encoding="utf-8"))
    for sid in want:
        if sid not in SETS:
            print("모르는 출처: %s" % sid)
            continue
        try:
            v = run(sid, (man["sources"].get(sid) or {}).get("total", 0), force)
        except Exception as e:
            print("%s — 실패: %s" % (sid, str(e)[:160]))
            continue
        if v:
            man["sources"][sid] = v
            json.dump(man, io.open(mpath, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
            print("    목록에 적었다", flush=True)
    print("\n전체 %s곳 · 출처 %d"
          % (format(sum(x["total"] for x in man["sources"].values()), ","),
             len(man["sources"])))


if __name__ == "__main__":
    main()
