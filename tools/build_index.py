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
PER_AREA = 6        # 한 도시가 오십 자리를 다 차지하지 않게
AREAS = 260

# 글자로 볼 것 — 숫자·라틴·한글·가나·한자·키릴·타이·아랍. 나머지는 낱말 경계로 친다
SPLIT = re.compile(r"[^0-9a-z가-힣぀-ヿ一-鿿"
                   r"Ѐ-ӿ฀-๿؀-ۿ]+")


# 한글·가나·한자는 글자 하나가 품은 뜻이 커서, 두 글자면 «성심»처럼 뭉뚱그려진다.
# 그래서 이 글자들로 된 낱말은 두 글자와 세 글자를 함께 담는다 —
# «성심당»을 치면 성심당만 든 칸이 따로 열린다
CJK = re.compile(r"[가-힣぀-ヿ一-鿿]")


def keys_of(word):
    # 한글·가나·한자는 세 글자로만 건다. 두 글자(«성심»)는 너무 뭉뚱그려져서
    # 한 칸에 성심돈·성심전·성심당이 다 몰리고, 둘 다 담으면 색인이 141 MB가 된다.
    # 라틴 글자는 두 글자로 건다 — 알파벳은 글자 하나가 품은 뜻이 작다.
    if CJK.match(word[0]):
        return [word[:3]] if len(word) >= 3 else [word[:2]]
    return [word[:2]]


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
                first = True
                for w in SPLIT.split(str(nm).lower()):
                    if len(w) < 2:
                        first = False
                        continue
                    head = first          # 이름의 첫 낱말에서 걸렸는가
                    first = False
                    if seen is None:
                        seen = set()
                    for p in keys_of(w):
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
                      if rec is None:
                        rec = [str(nm)[:44], round(la, 5), round(lo, 5), si]
                    # 첫 낱말에서 걸린 것과 이름이 짧은 것을 먼저 담는다.
                    # 자리가 차면 건너뛰는 게 아니라 **가장 못한 것을 밀어낸다** —
                    # 건너뛰면 가나다순으로 먼저 온 «디씨씨 성심당»이 여섯 자리를
                    # 다 차지하고, 정작 «성심당본점»은 들어올 자리가 없다
                      key = (0 if head else 1, len(rec[0]))
                      if len(L) < PER_AREA:
                        L.append((key[0], key[1], rec))
                      else:
                        wi = max(range(len(L)), key=lambda z: (L[z][0], L[z][1]))
                        if key < (L[wi][0], L[wi][1]):
                            L[wi] = (key[0], key[1], rec)
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
        picked = []
        lists = [sorted(v, key=lambda z: (z[0], z[1])) for v in areas.values()]
        i = 0
        while len(picked) < PER and any(lists):
            for L in lists:
                if not L:
                    continue
                picked.append(L.pop(0)[2])
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
    man["index"] = {"buckets": BUCKETS, "gram": 2, "cjk": 3, "per": PER, "places": True}
    json.dump(man, io.open(mpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("색인 %s곳 · %d개 꾸러미 · %.0f MB · 꾸러미 평균 %.0f KB"
          % (format(entries, ","), BUCKETS, nbytes / 1048576,
             nbytes / BUCKETS / 1024))


if __name__ == "__main__":
    main()
