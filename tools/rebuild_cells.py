# -*- coding: utf-8 -*-
"""칸 목록과 덮개를 **디스크에 있는 파일에서** 다시 만든다.

`split_manifest.py`를 이미 갈라 놓은 목록에 한 번 더 돌렸다. 그 목록에는 칸 열쇠가
없으므로(그게 가르는 목적이었다) 빈 것을 썼고, 출처 233개의 `cells.json`이 `{}`가
되고 덮개도 지워졌다. 화면 안 검색과 서비스 지역 색칠이 그 자리에서 멈춘다.

칸 파일 7만 8천 개는 그대로 있으므로, 목록이 아니라 **파일에서** 다시 세면 된다.
목록은 파일의 요약일 뿐이고, 요약이 틀리면 원본에서 다시 만든다.

Run: python tools/rebuild_cells.py
"""
import collections, io, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REG = os.path.join(os.path.dirname(REPO), "estela-data", "registry")
if not os.path.isdir(REG):
    REG = os.path.join(REPO, "data", "registry")


def rows_in(path):
    try:
        d = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return 0
    if isinstance(d, dict) and "p" in d:
        return len(d["p"])
    if isinstance(d, list):
        return len(d)
    return 0


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    mpath = os.path.join(REG, "manifest.json")
    man = json.load(io.open(mpath, encoding="utf-8"))
    fixed = ncells = 0
    for sid, v in sorted(man["sources"].items()):
        d = os.path.join(REG, *v["folder"].split("/"))
        if not os.path.isdir(d):
            print("  폴더 없음: %s" % sid)
            continue
        step = v.get("step") or man.get("step", 0.25)
        cells, total = {}, 0
        for f in os.listdir(d):
            if not f.endswith(".json") or f == "cells.json":
                continue
            n = rows_in(os.path.join(d, f))
            if n:
                cells[f[:-5]] = n
                total += n
        json.dump(cells, io.open(os.path.join(d, "cells.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
        cov = set()
        for k in cells:
            a, b = k.split("_")
            cov.add((int(math.floor(int(a) * step)), int(math.floor(int(b) * step))))
        v["cov"] = " ".join("%d,%d" % k for k in sorted(cov))
        v.pop("cells", None)
        if total:
            v["total"] = total
        ncells += len(cells)
        fixed += 1
        if fixed % 60 == 0:
            print("   %d개 출처 · 칸 %s" % (fixed, format(ncells, ",")), flush=True)
    json.dump(man, io.open(mpath, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("출처 %d · 칸 %s · 전체 %s곳 · manifest %.0f KB"
          % (fixed, format(ncells, ","),
             format(sum(x["total"] for x in man["sources"].values()), ","),
             os.path.getsize(mpath) / 1024))


if __name__ == "__main__":
    main()
