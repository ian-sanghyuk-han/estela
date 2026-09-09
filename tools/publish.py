# -*- coding: utf-8 -*-
"""자료 저장소를 올린다 — 역사를 쌓지 않고.

깃은 옛 판을 지우지 않는다. 자료 저장소는 785 MB, 색인 저장소는 584 MB이고, 달마다
다시 받으면 Overture 이름이 조금씩 바뀌면서 칸 파일 7만 8천 개가 거의 다 새 파일이
된다. 한 번에 300 MB 남짓이 역사에 쌓이고 **1년이면 4 GB**다. GitHub는 저장소 하나를
1 GB 아래로 두라고 하고, 그 위로는 경고를 보낸다.

그래서 갱신할 때마다 **뿌리 없는 커밋 하나로 갈아엎는다.** 잃는 것은 «지난달 판으로
되돌리기»인데, 그건 도구와 원본이 있으면 다시 만들 수 있다. 얻는 것은 저장소가 영영
한 판 크기로 머무는 것이다.

앱 저장소(estela)에는 절대 쓰지 않는다. 거기는 사람이 한 일이 쌓이는 곳이고, 역사가
곧 내용이다. 그래서 이름을 넣어도 거절한다.

Run: python tools/publish.py estela-data "무엇이 바뀌었는지 한 줄"
     python tools/publish.py estela-index "색인 다시 지음"
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(os.path.dirname(HERE))
ALLOWED = {"estela-data", "estela-index"}
NEVER = {"estela", "Estela"}


def run(args, cwd):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode:
        raise SystemExit("실패: %s\n%s%s" % (" ".join(args), p.stdout, p.stderr))
    return (p.stdout or "").strip()


def size_mb(path):
    n = 0
    for root, dirs, files in os.walk(path):
        if ".git" in dirs:
            dirs.remove(".git")
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n / 1048576.0


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    repo, msg = sys.argv[1], sys.argv[2]
    if repo in NEVER:
        raise SystemExit("앱 저장소는 역사를 지우지 않는다. 거기는 사람이 한 일이 쌓이는 곳이다.")
    if repo not in ALLOWED:
        raise SystemExit("아는 자료 저장소가 아니다: %s" % repo)
    d = os.path.join(WORK, repo)
    if not os.path.isdir(os.path.join(d, ".git")):
        raise SystemExit("저장소가 없다: %s" % d)

    before = run(["git", "count-objects", "-vH"], d)
    print("%s · 파일 %.0f MB" % (repo, size_mb(d)))
    for line in before.splitlines():
        if line.startswith("size-pack"):
            print("  갈아엎기 전 역사 %s" % line.split(":", 1)[1].strip())

    branch = "main"
    tmp = "publish-%d" % int(time.time())
    run(["git", "checkout", "--orphan", tmp], d)     # 뿌리 없는 가지 — 부모가 없다
    run(["git", "add", "-A"], d)
    run(["git", "commit", "-q", "-m",
         "%s\n\nRebuilt by tools/ on %s. This repository keeps no history: it is\n"
         "generated data, and a year of monthly copies would be several gigabytes\n"
         "of dead weight. The tools and the upstream sources are the record.\n\n"
         "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
         % (msg, time.strftime("%Y-%m-%d"))], d)
    run(["git", "branch", "-D", branch], d)
    run(["git", "branch", "-m", branch], d)
    run(["git", "reflog", "expire", "--expire=now", "--all"], d)
    run(["git", "gc", "--prune=now", "--quiet"], d)
    after = run(["git", "count-objects", "-vH"], d)
    for line in after.splitlines():
        if line.startswith("size-pack"):
            print("  갈아엎은 뒤 역사 %s" % line.split(":", 1)[1].strip())
    print("  올리는 중 — 통째로 다시 보내므로 오래 걸린다")
    run(["git", "push", "-f", "origin", branch], d)
    print("  올렸다: %s" % msg)


if __name__ == "__main__":
    main()
