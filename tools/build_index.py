# -*- coding: utf-8 -*-
"""전역 검색 색인 — 지도를 옮기지 않고도 이름으로 찾게 한다.

지금까지 검색은 화면에 걸친 칸만 뒤졌다. 개봉동을 알아야 개봉동 순대국을 찾을 수 있었고,
그러면 검색이라고 부르기 어렵다.

처음에는 «어느 땅에 있는지»만 담았다. 1°짜리 땅 하나 안에 세밀한 칸이 400개라, 그중
무엇을 펴야 하는지 알 수 없어서 엉뚱한 칸을 받아 왔다. 헛수고였다.

그래서 뒤집었다 — **색인이 가게를 직접 담는다.** 말머리마다 최대 50곳까지, 땅을 골고루.
말머리 216,651개 중 **92%가 스무 번 이하로만 나오므로**, 드문 이름은 사실상 전부 담긴다.
동영상에서 본 그 집을 찾는 일은 대개 드문 이름이다.

«카페»처럼 흔한 말머리는 세계에 흩어진 50곳만 보여 주고, 나머지는 그 동네로 가서 찾는다 —
화면 안 검색이 원래 그 일을 한다.

**말머리 두 글자**로만 잡는다. 이름 속 아무 데나(순대실록의 "실록") 찾으려면 모든 두 글자
토막을 담아야 하고, 그러면 색인이 자료만큼 커진다. 화면 안 검색은 지금처럼 아무 데나
걸리고, 전역 검색만 말머리로 건다.

땅은 1°로 잡는다. 그보다 잘면 색인이 자료만큼 커지고, 그보다 성기면 한 번에 받아야 할
칸이 너무 많아진다.

Run: python tools/build_index.py
"""
import io, json, math, os, re, sys, time, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REG = os.path.join(os.path.dirname(REPO), "estela-data", "registry")
if not os.path.isdir(REG):
    REG = os.path.join(REPO, "data", "registry")
OUT = os.path.join(REG, "index")
BUCKETS = 512
PER = 50            # 말머리 하나가 담는 가게 수 — 92%의 말머리는 이보다 적게 나온다
PER_AREA = 3        # 한 도시가 오십 자리를 다 차지하지 않게
AREAS = 260

# 글자로 볼 것 — 숫자·라틴·한글·가나·한자·키릴·타이·아랍. 나머지는 낱말 경계로 친다
SPLIT = re.compile(r"[^0-9a-z가-힣぀-ヿ一-鿿"
                   r"Ѐ-ӿ฀-๿؀-ۿ]+")


def bucket(prefix):
    return zlib.crc32(prefix.encode("utf-8")) % BUCKETS


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    mpath = os.path.join(REG, "manifest.json")
    man = json.load(io.open(mpath, encoding="utf-8"))
    srcs = sorted(man["sources"])
    si_of = {s: i for i, s in enumerate(srcs)}

    t0 = time.time()
    idx = {}                       # prefix -> {packed: count}
    names = cells = 0
    for n_done, sid in enumerate(srcs):
        v = man["sources"][sid]
        si = si_of[sid]
        d = os.path.join(REG, *v["folder"].split("/"))
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".json") or f == "cells.json":
                continue
            try:
                dd = json.load(io.open(os.path.join(d, f), encoding="utf-8"))
            except Exception:
                continue
            # 칸 파일이 두 형식이다. 압축 형식(v3)은 {o,k,p}이고, 그 전에 쪼갠
            # 정부 명부는 그냥 줄의 배열이다. 앞의 것만 읽다가 영국·프랑스·미국 도시
            # 48만 8,762곳을 통째로 빠뜨렸다 — 형식이 둘이면 둘 다 읽어야 한다
            if isinstance(dd, dict) and "p" in dd:
                y0, x0 = dd["o"]
                rows = [(r[0], y0 + r[1] / 1e5, x0 + r[2] / 1e5) for r in dd["p"]]
            elif isinstance(dd, list):
                rows = [(r[0], r[1], r[2]) for r in dd if len(r) >= 3]
            else:
                continue
            cells += 1
            for nm, la, lo in rows:
                names += 1
                area = (int(math.floor(la)), int(math.floor(lo)))
                rec = None
                seen = None
                for w in SPLIT.split(str(nm).lower()):
                    if len(w) < 2:
                        continue
                    p = w[:2]
                    if seen is None:
                        seen = set()
                    if p in seen:
                        continue
                    seen.add(p)
                    a = idx.get(p)
                    if a is None:
                        a = idx[p] = {}
                    L = a.get(area)
                    if L is None:
                        if len(a) >= AREAS:
                            continue          # 땅을 너무 많이 벌리지 않는다
                        L = a[area] = []
                    if len(L) >= PER_AREA:
                        continue
                    if rec is None:
                        rec = [str(nm)[:44], round(la, 5), round(lo, 5), si]
                    L.append(rec)
        if (n_done + 1) % 40 == 0:
            print("   출처 %d/%d · 이름 %s · 말머리 %s · %.0f분"
                  % (n_done + 1, len(srcs), format(names, ","),
                     format(len(idx), ","), (time.time() - t0) / 60), flush=True)

    print("읽기 끝: 칸 %s · 이름 %s · 말머리 %s · %.0f분"
          % (format(cells, ","), format(names, ","), format(len(idx), ","),
             (time.time() - t0) / 60))

    if os.path.isdir(OUT):
        import shutil
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    buckets = [{} for _ in range(BUCKETS)]
    entries = 0
    for p, areas in idx.items():
        total = sum(len(v) for v in areas.values())
        # 땅을 돌아가며 하나씩 집는다 — 한 도시가 오십 자리를 다 차지하지 않게
        picked, lists = [], [list(v) for v in areas.values()]
        i = 0
        while len(picked) < PER and any(lists):
            for L in lists:
                if not L:
                    continue
                picked.append(L.pop(0))
                if len(picked) >= PER:
                    break
            i += 1
            if i > PER + 5:
                break
        buckets[bucket(p)][p] = {"n": total, "p": picked}
        entries += len(picked)
    nbytes = 0
    for i, b in enumerate(buckets):
        q = os.path.join(OUT, "b%03d.json" % i)
        json.dump(b, io.open(q, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        nbytes += os.path.getsize(q)

    man["srcs"] = srcs
    man["index"] = {"buckets": BUCKETS, "gram": 2, "per": PER, "places": True}
    json.dump(man, io.open(mpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("색인 %s곳 · %d개 꾸러미 · %.0f MB · 꾸러미 평균 %.0f KB"
          % (format(entries, ","), BUCKETS, nbytes / 1048576,
             nbytes / BUCKETS / 1024))


if __name__ == "__main__":
    main()
