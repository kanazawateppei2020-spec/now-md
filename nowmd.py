#!/usr/bin/env python3
"""nowmd.py — build ONE page (NOW.md) that any AI (Claude, ChatGPT, Codex, Gemini…) reads first to know the current state.
複数のAIに引き継ぐための「いまの状況.md」を、小さなJSONの記録から機械で作る(AI不使用・標準ライブラリだけ)。

Each task = one small JSON file in ./tasks/ . Each AI (or you) writes its own line; nobody edits NOW.md by hand.

  python3 nowmd.py add    --who claude --title "Fix login bug" --status running
  python3 nowmd.py add    --who codex  --title "Write tests" --status blocked --why "needs API key" --fix "ask the owner for a test key"
  python3 nowmd.py update --id <id> --status blocked --why "waiting for review" --fix "ping the reviewer"
  python3 nowmd.py done   --id <id> [--result path/to/result.md]
  python3 nowmd.py note   "Decision: use SQLite, not Postgres"
  python3 nowmd.py build            # (re)writes NOW.md  — run it from cron every few minutes if you like
  python3 nowmd.py check            # lists broken task files / bad status / bad dates (exit 1 if any)
  python3 nowmd.py list             # one line per task: id, [status], title  (find the id for update/done)

Status: running | waiting | blocked | failed | done
Folder: --dir DIR (default: current folder; uses DIR/tasks/, DIR/notes.md, DIR/NOW.md)

Safe for several AIs writing at once: every write takes a lock file (DIR/.nowmd.lock),
ids never collide (random suffix + exclusive create), files are replaced atomically.
"""
import argparse, contextlib, datetime, glob, json, math, os, re, secrets, sys, time

__version__ = "0.2.3"
MAX_LINES = 120
STATUSES = ("running", "waiting", "blocked", "failed", "done")
LOCK_NAME = ".nowmd.lock"
# Seconds to wait for the lock / age after which a lock *may* be left over by a crashed process.
# Override with env NOWMD_LOCK_WAIT / NOWMD_LOCK_STALE. An old lock is only taken over if its owner process is gone.
LOCK_WAIT = 10.0
LOCK_STALE = 30.0
ID_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,119}")  # no leading dot, no slashes


def now():
    return datetime.datetime.now().astimezone()


def clip(t, n=100):
    return re.sub(r"\s+", " ", str(t)).strip()[:n]


def parse(s):
    """Parse an ISO time; naive times are treated as local time. Returns None if invalid."""
    try:
        d = datetime.datetime.fromisoformat(s)
        return d if d.tzinfo else d.astimezone()
    except (ValueError, OverflowError, OSError, TypeError):  # e.g. year 0001 / 9999 cannot be shifted to local time
        return None


def hm(s):
    d = parse(s)
    if not d:
        return "?"
    try:
        return d.astimezone().strftime("%m/%d %H:%M")
    except (ValueError, OverflowError, OSError):
        return "?"


def env_float(name, default):
    """A finite, non-negative number from the environment, else the default."""
    try:
        v = float(os.environ.get(name, default))
    except ValueError:
        return default
    return v if math.isfinite(v) and v >= 0 else default


def pid_alive(pid):
    """True if a process with this pid exists (best effort; unknown -> True so we never steal a live lock)."""
    if pid <= 0 or pid > 2**31 - 1:  # not a real pid (e.g. a corrupted lock file)
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return k.GetLastError() == 5  # access denied = exists
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return (not ok) or code.value == 259  # STILL_ACTIVE
        except Exception:
            return True
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError, ValueError):
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def read_lock_owner(path):
    """Returns (raw text, pid or None) of a lock file."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return "", None
    try:
        return raw, int(raw.split()[0])
    except (ValueError, IndexError):
        return raw, None


@contextlib.contextmanager
def lock(base):
    """Cross-platform lock: create DIR/.nowmd.lock exclusively (content: "<pid> <unix time>").
    An old lock is taken over only when it is older than the stale limit AND its owner process is gone."""
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, LOCK_NAME)
    wait, stale = env_float("NOWMD_LOCK_WAIT", LOCK_WAIT), env_float("NOWMD_LOCK_STALE", LOCK_STALE)
    mine = f"{os.getpid()} {time.time():.0f}"
    t0 = time.time()
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, mine.encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) > stale:
                    raw, pid = read_lock_owner(path)
                    if pid is None or not pid_alive(pid):
                        # re-check the owner didn't change while we looked, then clear the dead lock
                        if read_lock_owner(path)[0] == raw:
                            os.remove(path)
                        continue
            except OSError:
                continue
            if time.time() - t0 > wait:
                raise SystemExit(f"could not get the lock ({path}); if no other nowmd is running, delete that file")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            if read_lock_owner(path)[0] == mine:  # never remove a lock somebody else now owns
                os.remove(path)
        except OSError:
            pass


def read_task(path):
    """Returns (dict or None, problem or None)."""
    try:
        with open(path, encoding="utf-8-sig") as f:  # -sig: tolerate a BOM (Windows editors)
            d = json.load(f)
    except Exception as e:
        return None, f"not valid JSON ({type(e).__name__})"
    if not isinstance(d, dict):
        return None, "top level is not an object"
    return d, None


def problems_of(d):
    """Human-readable problems of one task dict."""
    out = []
    for k in ("id", "who", "title"):
        if not str(d.get(k, "")).strip():
            out.append(f"missing '{k}'")
    if d.get("status", "waiting") not in STATUSES:
        out.append(f"unknown status '{d.get('status')}' (use {'|'.join(STATUSES)})")
    for k in ("started", "updated"):
        if k in d and parse(str(d[k])) is None:
            out.append(f"bad time in '{k}': {clip(d[k], 30)}")
    return out


def load_tasks(base):
    out = []
    for f in sorted(glob.glob(os.path.join(base, "tasks", "*.json"))):
        d, _ = read_task(f)
        if d is not None:
            out.append(d)
    return out


def list_lines(base):
    """One line per readable task: '<id>  [status]  title' (the id is what --id wants)."""
    out = []
    for f in sorted(glob.glob(os.path.join(base, "tasks", "*.json"))):
        d, prob = read_task(f)
        if prob:
            continue
        out.append(f"{os.path.basename(f)[:-5]}  [{clip(d.get('status', 'waiting'), 10)}]  {clip(d.get('title', ''), 60)}")
    return out


def check(base):
    """Returns a list of 'file: problem' strings."""
    bad = []
    for f in sorted(glob.glob(os.path.join(base, "tasks", "*.json"))):
        d, prob = read_task(f)
        name = os.path.basename(f)
        if prob:
            bad.append(f"{name}: {prob}")
            continue
        for p in problems_of(d):
            bad.append(f"{name}: {p}")
    return bad


def write_json_atomic(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def check_id(tid):
    """One id check for every command. Exits with a message if the id could escape tasks/ or is odd."""
    if not isinstance(tid, str) or not ID_RE.fullmatch(tid):
        sys.exit("--id may only use letters, digits, _ . - (max 120, must not start with '.' or contain '/')")
    return tid


def task_path(base, tid):
    """Path of tasks/<id>.json after validating the id and confirming it stays inside tasks/."""
    check_id(tid)
    root = os.path.realpath(os.path.join(base, "tasks"))
    p = os.path.realpath(os.path.join(root, tid + ".json"))
    if os.path.dirname(p) != root:
        sys.exit("--id resolves outside the tasks folder")
    return p


def new_task_id(base, who, stamp):
    """Unique id: time + who + 4 random hex; the file is reserved with exclusive create."""
    os.makedirs(os.path.join(base, "tasks"), exist_ok=True)
    who_part = re.sub(r"[^a-z0-9]+", "", who.lower())[:8] or "x"
    for _ in range(100):
        tid = f"{stamp}_{who_part}_{secrets.token_hex(2)}"
        p = os.path.join(base, "tasks", tid + ".json")
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return tid
        except FileExistsError:
            continue
    raise SystemExit("could not make a unique id")


def build(base, stale_min=60):
    n = now()
    tasks = load_tasks(base)
    warn = len(check(base))
    running, stuck, done = [], [], []
    for t in tasks:
        st = t.get("status", "waiting")
        title, who = clip(t.get("title", ""), 60), clip(t.get("who", "?"), 30)
        upd = parse(str(t.get("updated", "")))
        if st == "running":
            stale = upd and (n - upd).total_seconds() > stale_min * 60
            running.append(f"- {title} ({who}) since {hm(t.get('started') or t.get('updated'))}" + (f"  ⚠ no update for {stale_min}+ min — check it" if stale else ""))
        elif st in ("blocked", "failed", "waiting"):
            line = f"- [{st}] {title} ({who}) — why: {clip(t.get('why', '?'), 70)}"
            if t.get("fix"):
                line += f" / how to unblock: {clip(t['fix'], 70)}"
            stuck.append(line)
        elif st == "done" and upd and upd > n - datetime.timedelta(hours=24):
            r = f" → {clip(t['result'], 100)}" if t.get("result") else ""
            done.append((upd, f"- {hm(t.get('updated'))} {title} ({who}){r}"))
    done = [x[1] for x in sorted(done, key=lambda x: x[0], reverse=True)]
    notes = []
    try:
        with open(os.path.join(base, "notes.md"), encoding="utf-8") as f:
            notes = [clip(l.rstrip(), 160) for l in f if l.startswith("- ")][-10:]
    except Exception:
        pass

    def sec(title, lines):
        return ["", f"## {title}"] + (lines or ["- none"])

    head = f"- built: {n:%Y-%m-%d %H:%M}   / read this one page first; details live in each task's result file"
    out = ["# NOW (written by a script — do not edit by hand)", head]
    if warn:
        out.append(f"- ⚠ {warn} broken task record(s) skipped — run `python3 nowmd.py check`")
    out += sec("Running", running) + sec("Stuck (and how to unblock)", stuck) + sec("Done in the last 24h", done[:12]) + sec("Latest notes / decisions", notes)
    flat = "\n".join(out).splitlines()  # count real lines, whatever the fields contained
    lines = flat[:MAX_LINES - 1] + ([f"…({len(flat) - (MAX_LINES - 1)}行省略 / lines omitted)"] if len(flat) > MAX_LINES else [])
    path = os.path.join(base, "NOW.md")
    tmp = path + f".{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
    return path, len(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build NOW.md for AI handoff")
    ap.add_argument("cmd", choices=["add", "update", "done", "note", "build", "check", "list"])
    ap.add_argument("text", nargs="?")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--who"); ap.add_argument("--title"); ap.add_argument("--status")
    ap.add_argument("--why"); ap.add_argument("--fix"); ap.add_argument("--id"); ap.add_argument("--result")
    ap.add_argument("--version", action="version", version="nowmd " + __version__)
    a = ap.parse_args(argv)
    base = os.path.abspath(a.dir)
    n = now().isoformat(timespec="seconds")

    if a.cmd == "check":
        with lock(base):  # read under the lock so a half-written record is not reported as broken
            bad = check(base)
        for b in bad:
            print(b)
        print(f"{len(bad)} problem(s)" if bad else "ok: no problems")
        return 1 if bad else 0

    if a.cmd == "list":
        with lock(base):
            rows = list_lines(base)
        print("\n".join(rows) if rows else "no tasks")
        return 0

    with lock(base):
        if a.cmd == "add":
            status = a.status or "running"
            a.who = clip(a.who, 30) if a.who else a.who  # one short line, so it cannot fake headings in NOW.md
            a.title = a.title.strip() if a.title else a.title  # a blank title is no title
            if not (a.who and a.title):
                sys.exit("add needs --who and --title")
            if status not in STATUSES:
                sys.exit("status: " + "|".join(STATUSES))
            tid = a.id
            if tid:
                if os.path.exists(task_path(base, tid)):
                    sys.exit(f"id already exists: {tid}")
            else:
                tid = new_task_id(base, a.who, now().strftime("%Y%m%d_%H%M%S"))
            d = {"id": tid, "who": a.who, "title": a.title, "status": status, "started": n, "updated": n}
            if a.why: d["why"] = a.why
            if a.fix: d["fix"] = a.fix
            write_json_atomic(task_path(base, tid), d)
            print("added", tid)
        elif a.cmd in ("update", "done"):
            if not a.id:
                sys.exit(f"{a.cmd} needs an existing --id")
            p = task_path(base, a.id)
            if not os.path.exists(p):
                sys.exit(f"{a.cmd} needs an existing --id")
            d, prob = read_task(p)
            if prob:
                sys.exit(f"{a.id}.json is broken: {prob}")
            if a.cmd == "done":
                d["status"] = "done"
            else:
                if a.status:
                    if a.status not in STATUSES:
                        sys.exit("status: " + "|".join(STATUSES))
                    d["status"] = a.status
                if a.title: d["title"] = a.title
                if not any((a.status, a.title, a.why, a.fix, a.result)):
                    sys.exit("update needs at least one of --status --title --why --fix --result")
            if a.why: d["why"] = a.why
            if a.fix: d["fix"] = a.fix
            if a.result: d["result"] = a.result
            if d.get("status") in ("running", "done"):
                # leaving a stuck state: the old reason no longer applies unless re-given
                if a.cmd == "update" and a.status and not a.why: d.pop("why", None)
                if a.cmd == "update" and a.status and not a.fix: d.pop("fix", None)
            d["updated"] = n
            write_json_atomic(p, d)
            print(a.cmd, a.id, "->", d.get("status"))
        elif a.cmd == "note":
            if not a.text:
                sys.exit('note needs text: nowmd.py note "..."')
            with open(os.path.join(base, "notes.md"), "a", encoding="utf-8") as f:
                f.write(f"- {now():%m/%d %H:%M} {clip(a.text, 150)}\n")
            print("noted")
        path, k = build(base)
    print(f"wrote {path} ({k} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
