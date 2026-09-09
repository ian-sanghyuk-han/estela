# -*- coding: utf-8 -*-
"""목록을 둘로 가른다 — 첫 화면에 필요한 것만 앞에, 나머지는 필요할 때.

manifest에 78,046개 칸 열쇠가 전부 들어 있어서 파일이 1 MB가 되었고, 브라우저는 그걸
첫 화면에서 통째로 읽었다. 그중 실제로 쓰이는 것은 지금 보고 있는 화면에 걸친 몇 개뿐이다.

가른 뒤:

- `manifest.json` — 출처마다 이름·나라·격자·라이선스와 **1°짜리 성긴 덮개**만.
  덮개는 서비스 지역을 칠하는 데 쓰고, 어느 출처를 들춰 볼지 고르는 데도 쓴다.
- `<folder>/cells.json` — 그 출처의 세밀한 칸 목록. 화면이 그 위에 왔을 때만 받는다.

성긴 덮개를 1°로 잡은 이유는, 그보다 잘게 잡으면 결국 원래 크기로 돌아가고, 그보다
성기게 잡으면 사막까지 덮었다고 말하게 되기 때문이다.

Run: python tools/split_manifest.py
"""
import collections, io, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REG = os.path.join(os.path.dirname(REPO), "estela-data", "registry")
if not os.path.isdir(REG):
    REG = os.path.join(REPO, "data", "registry")


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    mpath = os.path.join(REG, "manifest.json")
    man = json.load(io.open(mpath, encoding="utf-8"))
    before = os.path.getsize(mpath)
    lite = {"version": 4, "step": man.get("step", 0.25), "cov": 1.0, "sources": {}}
    ncells = nbytes = 0
    for sid, v in man["sources"].items():
        cells = v.get("cells") or {}
        step = v.get("step") or man.get("step", 0.25)
        # 세밀한 칸 목록은 그 출처의 폴더로 내려보낸다
        d = os.path.join(REG, *v["folder"].split("/"))
        if not os.path.isdir(d):
            os.makedirs(d)
        p = os.path.join(d, "cells.json")
        if not cells:
            # 이미 갈라 놓은 목록에 한 번 더 돌면 여기가 빈다. 그대로 쓰면 출처
            # 233개의 칸 목록과 덮개가 «{}»가 되고 화면 안 검색이 그 자리에서
            # 멈춘다 — 한 번 그렇게 했다. 이미 내려간 것이 있으면 손대지 않는다
            if os.path.exists(p):
                try:
                    old = json.load(io.open(p, encoding="utf-8"))
                except Exception:
                    old = {}
                if old:
                    ncells += len(old)
                    nbytes += os.path.getsize(p)
                    w = dict(v)
                    w.pop("cells", None)
                    if not w.get("cov"):
                        cov = collections.Counter()
                        for k in old:
                            a, b = k.split("_")
                            cov[(int(math.floor(int(a) * step)),
                                 int(math.floor(int(b) * step)))] += old[k]
                        w["cov"] = " ".join("%d,%d" % k for k in sorted(cov))
                    lite["sources"][sid] = w
                    continue
        json.dump(cells, io.open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        ncells += len(cells)
        nbytes += os.path.getsize(p)
        # 1°짜리 덮개 — 어느 땅을 덮는지만. 안에 몇 곳인지는 여기서 세지 않는다
        cov = collections.Counter()
        for k in cells:
            a, b = k.split("_")
            cov[(int(math.floor(int(a) * step)), int(math.floor(int(b) * step)))] += cells[k]
        w = dict(v)
        w.pop("cells", None)
        w["cov"] = " ".join("%d,%d" % k for k in sorted(cov))
        lite["sources"][sid] = w
    json.dump(lite, io.open(mpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    after = os.path.getsize(mpath)
    import gzip
    gz = len(gzip.compress(open(mpath, "rb").read(), 6))
    print("manifest %.0f KB → %.0f KB (gzip %.0f KB)" % (before / 1024, after / 1024, gz / 1024))
    print("세밀한 칸 %s개를 %d개 파일로 내려보냄 · %.1f MB"
          % (format(ncells, ","), len(man["sources"]), nbytes / 1048576))


if __name__ == "__main__":
    main()
