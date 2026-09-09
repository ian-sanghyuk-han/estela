# -*- coding: utf-8 -*-
"""전역 검색 색인 — 사전을 찾듯이.

앞선 판은 말머리를 **정해진 길이**로 잘랐다. 라틴 글자는 두 글자, 한글은 세 글자.
그래서 «tr» 한 칸에 30만 곳이 몰렸고 그중 50곳만 담기니 «Trattoria Dari»는 아무리
쳐도 나오지 않았다. 고치겠다고 «tr» 안에 그 집이 들어가도록 순위를 손보려 했는데,
선장님이 그건 거꾸로라고 하셨다. 맞는 말이다 — 사전은 «tr» 쪽에 그 낱말을 끌어다
놓지 않는다. 사전은 t·r·a·t·t 를 따라 **책장을 좁혀 준다.**

그래서 이 판은 **말머리마다 칸을 만들되, 넘치면 더 깊이 판다.**

- 어떤 말머리에 50곳 이하가 걸리면 그 칸에 **전부** 담는다. 빠지는 게 없다.
- 50곳을 넘으면 그 칸에는 **숫자만** 둔다("밑에 30만 곳"). 이름은 한 글자 더 긴
  칸으로 내려간다. 유저가 글자를 더 치면 그 칸이 열린다.
- 열두 글자까지 파고, 거기서도 넘치면 그때만 50곳을 고른다.

넘치지 않는 말머리라도 **부모가 넘쳤을 때만** 칸을 만든다. 부모 칸에 이미 전부
들어 있으면 자식 칸은 같은 것을 한 번 더 담는 셈이다.

**숫자만 두는 칸도 자기 이름과 똑같은 낱말은 들고 있는다.** 여덟 글자에서 끊었을 때
«Trattoria Dari»가 안 나왔다. dari 밑에 darius·daria가 넘쳐서 이름이 더 깊은 칸으로
내려갔는데, dari 라는 낱말은 네 글자뿐이라 내려갈 칸이 없어 나무에서 떨어져 나갔다.
사전에서도 dari 쪽을 펴면 표제어 dari 가 daria 위에 있다. 순대실록(51곳)과
El Celler de Can Roca 도 같은 자리에서 떨어졌었다.

**낱말이 전부 흔한 이름은 이어 붙여서도 건다.** 세상 식당 이름의 43.4%가 그렇다 —
Trattoria Dari, Le Bistro, Golden Dragon. 흔한 낱말은 2,861,053개 중 34,185개뿐인데
그것들이 이름의 절반을 덮는다. 어느 낱말로도 좁혀지지 않으니 사전이라면 이름 전체로
찾을 자리다. 그런 이름만 골라 붙이면 196 MB가 더 든다. 전부 붙이면 355 MB다.

넘치는 칸의 차례는 **사전의 차례**다 — 친 것과 똑같은 낱말이 먼저, 그다음 가나다순,
땅은 골고루. 인기나 유명세로 고르지 않는다. 그건 유저가 생긴 뒤에 정할 문제고,
그때 정하더라도 이 차례와 다투지 않는다.

칸이 100만 개라 꾸러미를 512개로 두면 하나가 600 KB가 된다. 4,096개로 늘려 하나를
75 KB 안팎으로 맞춘다 — 한 글자 칠 때마다 그만큼만 받으면 된다.

여유 메모리가 6 GB뿐이라 나눠 읽는다. 여덟 글자까지는 한 번에 세고, 그보다 깊은
층은 넘치는 자리에만 생기므로 한 층씩 따로 센다. 채울 때도 꾸러미를 넷으로 갈라
한 번에 4분의 1씩만 들고 있는다.

Run: python tools/build_index.py
"""
import collections, io, json, math, os, re, shutil, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REG = os.path.join(os.path.dirname(REPO), "estela-data", "registry")
if not os.path.isdir(REG):
    REG = os.path.join(REPO, "data", "registry")
# 색인 300 MB는 자료 저장소에 안 들어간다 — 제 저장소를 쓴다
OUT = os.path.join(os.path.dirname(REPO), "estela-index", "index")
if not os.path.isdir(os.path.dirname(OUT)):
    OUT = os.path.join(REG, "index")

BUCKETS = 8192      # 칸이 늘어난 만큼 꾸러미도 늘린다 — 하나를 75 KB 안팎으로
CAP = 50            # 이보다 적게 걸리면 그 칸에 전부 담는다
MIND = 2            # 두 글자 밑으로는 칸을 만들지 않는다
BASE = 8            # 여기까지는 한 번에 센다
MAXD = 12           # 여기까지 판다. 깊은 층은 넘치는 자리에만 생기므로 거의 공짜다
PER_AREA = 6        # 넘치는 칸에서만 쓴다 — 한 도시가 오십 자리를 다 차지하지 않게
SHARDS = 4

SPLIT = re.compile(r"[^0-9a-z가-힣぀-ヿ一-鿿"
                   r"Ѐ-ӿ฀-๿؀-ۿ]+")


def bucket(prefix):
    return zlib.crc32(prefix.encode("utf-8")) % BUCKETS


def cell_rows(path):
    """칸 파일 두 형식을 다 읽는다 — 압축 형식(v3)과 그 전의 줄 배열."""
    try:
        dd = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return ()
    if isinstance(dd, dict) and "p" in dd:
        y0, x0 = dd["o"]
        return [(r[0], y0 + r[1] / 1e5, x0 + r[2] / 1e5) for r in dd["p"]]
    if isinstance(dd, list):
        return [(r[0], r[1], r[2]) for r in dd if len(r) >= 3]
    return ()


def walk(man, srcs):
    """모든 출처의 모든 칸을 흘려보낸다. 출처가 끝날 때 (None, 번호)를 낸다."""
    for si, sid in enumerate(srcs):
        v = man["sources"][sid]
        d = os.path.join(REG, *v["folder"].split("/"))
        if os.path.isdir(d):
            for f in os.listdir(d):
                if not f.endswith(".json") or f == "cells.json":
                    continue
                for nm, la, lo in cell_rows(os.path.join(d, f)):
                    yield nm, la, lo, si
        yield None, si, 0.0, 0


COMMON = set()      # 쉰 번 넘게 나오는 낱말. 첫 번째 읽기에서 채운다


def words(nm):
    return [w for w in SPLIT.split(str(nm).lower()) if len(w) >= MIND]


def tokens(nm):
    """색인에 걸 (글자줄, 몇 글자부터 걸 것인가).

    보통은 낱말 하나하나다. 그런데 세상 식당 이름의 **43.4%는 흔한 낱말로만** 되어
    있다 — Trattoria Dari, Le Bistro, Golden Dragon. 어느 낱말로도 좁혀지지 않는다.
    사전이라면 그건 «이름 전체»로 찾을 자리다. 그래서 그런 이름만 낱말을 이어 붙여
    한 줄로 만들어 함께 건다. 첫 낱말보다 긴 자리부터만 — 그보다 짧으면 첫 낱말의
    말머리와 똑같아서 두 번 담는 셈이다."""
    ws = words(nm)
    out = [(w, MIND) for w in ws]
    if len(ws) >= 2 and all(w in COMMON for w in ws):
        out.append(("".join(ws), len(ws[0]) + 1))
    return out


def prefixes(nm, top=MAXD):
    """이름에서 뽑을 (말머리, 그 말머리가 나온 글자줄)."""
    out, seen = [], set()
    for s, lo in tokens(nm):
        for L in range(lo, min(len(s), top) + 1):
            p = s[:L]
            if p not in seen:
                seen.add(p)
                out.append((p, s))
    return out




def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    mpath = os.path.join(REG, "manifest.json")
    man = json.load(io.open(mpath, encoding="utf-8"))
    srcs = sorted(man["sources"])
    t0 = time.time()

    # ── 세기 ⓪: 흔한 낱말을 가려낸다 ───────────────────────────────────
    # 낱말 하나가 쉰 번 이하로만 나오면 그 이름은 그 낱말로 이미 찾아진다.
    # 이어 붙이기가 필요한 것은 낱말이 **전부** 흔한 이름뿐이다
    wc = collections.Counter()
    for nm, la, lo, si in walk(man, srcs):
        if nm is not None:
            wc.update(set(words(nm)))
    for w, c in wc.items():
        if c > CAP:
            COMMON.add(w)
    print("낱말 %s개 중 흔한 것 %s개 · %.0f분"
          % (format(len(wc), ","), format(len(COMMON), ","),
             (time.time() - t0) / 60), flush=True)
    del wc

    # ── 세기 ①: 여덟 글자까지 한 번에 ──────────────────────────────────
    cnt = collections.Counter()
    n = 0
    for nm, la, lo, si in walk(man, srcs):
        if nm is None:
            if (si + 1) % 60 == 0 or si + 1 == len(srcs):
                print("   세는 중 %d/%d · 이름 %s · 말머리 %s · %.0f분"
                      % (si + 1, len(srcs), format(n, ","), format(len(cnt), ","),
                         (time.time() - t0) / 60), flush=True)
            continue
        n += 1
        cnt.update(p for p, w in prefixes(nm, BASE))
    print("세기 끝: 이름 %s · 여덟 글자까지의 말머리 %s · %.0f분"
          % (format(n, ","), format(len(cnt), ","), (time.time() - t0) / 60), flush=True)

    leaf, deep = {}, {}                # 전부 담는 칸 / 숫자만 두는 칸
    big = set(p for p, c in cnt.items() if c > CAP)
    for p, c in cnt.items():
        if c <= CAP:
            # 부모가 넘쳤을 때만 칸을 만든다. 부모에 이미 전부 들어 있으면 군더더기다
            if len(p) == MIND or p[:-1] in big:
                leaf[p] = c
        else:
            deep[p] = c
    front = set(p for p in big if len(p) == BASE)
    del cnt, big

    # ── 세기 ②: 여덟 글자에서 넘친 자리만 한 층씩 더 판다 ──────────────
    d = BASE
    while front and d < MAXD:
        d += 1
        sub = collections.Counter()
        for nm, la, lo, si in walk(man, srcs):
            if nm is None:
                continue
            seen = None
            for s, lo in tokens(nm):
                if len(s) < d or d < lo or s[:d - 1] not in front:
                    continue
                p = s[:d]
                if seen is None:
                    seen = set()
                if p not in seen:
                    seen.add(p)
                    sub[p] += 1
        nxt = set()
        for p, c in sub.items():
            if c > CAP and d < MAXD:
                deep[p] = c
                nxt.add(p)
            else:
                leaf[p] = c            # 열두 글자에서도 넘치면 여기서 오십 곳을 고른다
        print("   %d글자 층 · 칸 %s · 더 깊이 %s · %.0f분"
              % (d, format(len(sub) - len(nxt), ","), format(len(nxt), ","),
                 (time.time() - t0) / 60), flush=True)
        front = nxt

    print("칸 %s개 · 숫자만 두는 칸 %s개 · 담을 항목 %s개"
          % (format(len(leaf), ","), format(len(deep), ","),
             format(sum(min(v, CAP) for v in leaf.values()), ",")), flush=True)

    # ── 채우기: 정해진 칸만. 여유 메모리 때문에 꾸러미를 넷으로 갈라 돈다 ──
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    over = set(p for p, c in leaf.items() if c > CAP)
    nbytes = entries = 0
    filled = set()                     # 낱말을 실제로 담은 «숫자만» 칸
    for sh in range(SHARDS):
        mineL = set(p for p in leaf if bucket(p) % SHARDS == sh)
        mineD = set(p for p in deep if bucket(p) % SHARDS == sh)
        box = {}
        for nm, la, lo, si in walk(man, srcs):
            if nm is None:
                continue
            rec = None
            for p, w in prefixes(nm):
                inL = p in mineL
                # 숫자만 두는 칸이라도 **자기 이름과 똑같은 낱말**은 들고 있어야 한다.
                # «dari»는 네 글자뿐이라 더 깊은 칸으로 내려갈 수가 없다. 사전에서도
                # dari 쪽을 펴면 표제어 dari 가 daria 위에 있다
                inD = (not inL) and p == w and p in mineD
                if not (inL or inD):
                    continue
                if rec is None:
                    rec = [str(nm)[:44], round(la, 5), round(lo, 5), si]
                L = box.get(p)
                if L is None:
                    L = box[p] = ([] if (inL and p not in over) else {})
                if isinstance(L, list):
                    L.append(rec)
                    continue
                # 넘치는 칸 — 친 것과 똑같은 낱말이 먼저, 그다음 가나다순.
                # 땅은 골고루 훑는다. 한 도시가 쉰 자리를 다 차지하지 않게
                a = (int(math.floor(la)), int(math.floor(lo)))
                q = L.get(a)
                if q is None:
                    if len(L) >= 200:
                        continue
                    q = L[a] = []
                key = (len(w), w, rec[0])
                if len(q) < PER_AREA:
                    q.append((key, rec))
                else:
                    wi = max(range(len(q)), key=lambda z: q[z][0])
                    if key < q[wi][0]:
                        q[wi] = (key, rec)
        packs = collections.defaultdict(dict)
        for p, L in box.items():
            if isinstance(L, dict):
                lists = [sorted(v, key=lambda z: z[0]) for v in L.values()]
                picked = []
                while len(picked) < CAP and any(lists):
                    for q in lists:
                        if q:
                            picked.append(q.pop(0)[1])
                            if len(picked) >= CAP:
                                break
            else:
                picked = L
            picked.sort(key=lambda r: r[0])
            if p in deep:
                packs[bucket(p)][p] = {"n": deep[p], "p": picked, "x": 1}
                filled.add(p)
            else:
                packs[bucket(p)][p] = {"n": leaf[p], "p": picked}
            entries += len(picked)
        for b, dd in packs.items():
            q = os.path.join(OUT, "b%04d.json" % b)
            json.dump(dd, io.open(q, "w", encoding="utf-8"),
                      ensure_ascii=False, separators=(",", ":"))
            nbytes += os.path.getsize(q)
        del box, packs, mineL, mineD
        print("   %d/%d 묶음 완료 · 지금까지 %.0f MB · %.0f분"
              % (sh + 1, SHARDS, nbytes / 1048576, (time.time() - t0) / 60), flush=True)

    # ── 낱말을 하나도 못 담은 «숫자만» 칸은 숫자만 적어 얹는다 ────────────
    add = collections.defaultdict(dict)
    for p, c in deep.items():
        if p not in filled:
            add[bucket(p)][p] = {"n": c}
    for b, dd in add.items():
        q = os.path.join(OUT, "b%04d.json" % b)
        cur = {}
        if os.path.exists(q):
            cur = json.load(io.open(q, encoding="utf-8"))
            nbytes -= os.path.getsize(q)
        cur.update(dd)
        json.dump(cur, io.open(q, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        nbytes += os.path.getsize(q)

    # 색인의 규격은 색인 저장소가 들고 있는다. 자료 저장소의 목록에 적어 두면 둘을
    # 같은 순간에 올려야 하고, 어긋난 몇 분 동안 검색이 조용히 빗나간다
    meta = {"buckets": BUCKETS, "min": MIND, "max": MAXD, "cap": CAP,
            "dict": True, "built": time.strftime("%Y-%m-%d"), "srcs": srcs}
    json.dump(meta, io.open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))

    nfiles = len([f for f in os.listdir(OUT) if f.endswith(".json")])
    man["srcs"] = srcs
    man["index"] = dict(meta)
    man["index"].pop("srcs", None)
    json.dump(man, io.open(mpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("색인 %s곳 · 꾸러미 %d개 · %.0f MB · 평균 %.0f KB · %.0f분"
          % (format(entries, ","), nfiles, nbytes / 1048576,
             nbytes / max(1, nfiles) / 1024, (time.time() - t0) / 60))


if __name__ == "__main__":
    main()
