"""Run: python3 -m unittest discover -s tests -v   (from the repo root)"""
import concurrent.futures, contextlib, glob, io, json, os, subprocess, sys, tempfile, unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import nowmd  # noqa: E402


def run(d, *args):
    """Call main() in-process; returns (exit_code, stdout)."""
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf):
        try:
            code = nowmd.main(["--dir", d, *args]) or 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
    return code, buf.getvalue()


def task_files(d):
    return sorted(glob.glob(os.path.join(d, "tasks", "*.json")))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class Basic(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = self.t.name

    def tearDown(self):
        self.t.cleanup()

    def add(self, *a):
        _, out = run(self.d, "add", *a)
        return out.split()[1]

    def test_add_build(self):
        self.add("--who", "claude", "--title", "Fix login")
        now = read(os.path.join(self.d, "NOW.md"))
        self.assertIn("## Running", now)
        self.assertIn("Fix login (claude)", now)

    def test_update_to_blocked_and_back(self):
        tid = self.add("--who", "codex", "--title", "Tests")
        run(self.d, "update", "--id", tid, "--status", "blocked", "--why", "needs key", "--fix", "ask owner")
        now = read(os.path.join(self.d, "NOW.md"))
        self.assertIn("[blocked] Tests (codex) — why: needs key / how to unblock: ask owner", now)
        run(self.d, "update", "--id", tid, "--status", "running")
        d = json.loads(read(task_files(self.d)[0]))
        self.assertEqual(d["status"], "running")
        self.assertNotIn("why", d)

    def test_update_needs_something_and_real_id(self):
        tid = self.add("--who", "a", "--title", "t")
        self.assertNotEqual(run(self.d, "update", "--id", tid)[0], 0)
        self.assertNotEqual(run(self.d, "update", "--id", "nope", "--status", "done")[0], 0)
        self.assertNotEqual(run(self.d, "update", "--id", tid, "--status", "bogus")[0], 0)

    def test_done_with_result(self):
        tid = self.add("--who", "a", "--title", "t")
        run(self.d, "done", "--id", tid, "--result", "r.md")
        self.assertIn("→ r.md", read(os.path.join(self.d, "NOW.md")))

    def test_same_second_same_who_no_collision(self):
        ids = {self.add("--who", "claude", "--title", "t%d" % i) for i in range(30)}
        self.assertEqual(len(ids), 30)
        self.assertEqual(len(task_files(self.d)), 30)

    def test_explicit_id_duplicate_rejected(self):
        self.add("--who", "a", "--title", "t", "--id", "x1")
        self.assertNotEqual(run(self.d, "add", "--who", "a", "--title", "t", "--id", "x1")[0], 0)
        self.assertNotEqual(run(self.d, "add", "--who", "a", "--title", "t", "--id", "../evil")[0], 0)

    def test_note(self):
        run(self.d, "note", "Decision: SQLite")
        self.assertIn("Decision: SQLite", read(os.path.join(self.d, "NOW.md")))


class Validation(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = self.t.name
        os.makedirs(os.path.join(self.d, "tasks"))

    def tearDown(self):
        self.t.cleanup()

    def put(self, name, text):
        with open(os.path.join(self.d, "tasks", name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_check_ok_when_empty(self):
        self.assertEqual(run(self.d, "check")[0], 0)

    def test_check_finds_problems_and_build_survives(self):
        self.put("a.json", "{not json")
        self.put("b.json", json.dumps({"id": "b", "who": "x", "title": "t", "status": "weird"}))
        self.put("c.json", json.dumps({"id": "c", "who": "x", "title": "t", "status": "running", "updated": "yesterday-ish"}))
        self.put("d.json", "[1,2]")
        code, out = run(self.d, "check")
        self.assertEqual(code, 1)
        for s in ("a.json", "unknown status", "bad time", "not an object"):
            self.assertIn(s, out)
        self.assertEqual(run(self.d, "build")[0], 0)
        self.assertIn("broken task record", read(os.path.join(self.d, "NOW.md")))

    def test_check_warns_when_id_does_not_match_file_name(self):
        self.put("good.json", json.dumps({"id": "good", "who": "x", "title": "t", "status": "running"}))
        self.assertEqual(run(self.d, "check")[0], 0)
        self.put("renamed.json", json.dumps({"id": "original", "who": "x", "title": "t", "status": "running"}))
        code, out = run(self.d, "check")
        self.assertEqual(code, 1)
        self.assertIn("renamed.json", out)
        self.assertIn("does not match the file name", out)
        self.assertNotIn("good.json", out)

    def test_naive_time_ok(self):
        self.put("e.json", json.dumps({"id": "e", "who": "x", "title": "t", "status": "running", "updated": "2020-01-01T00:00:00"}))
        self.assertEqual(run(self.d, "check")[0], 0)
        run(self.d, "build")
        self.assertIn("no update for", read(os.path.join(self.d, "NOW.md")))


def _worker(args):
    d, i = args
    r = subprocess.run([sys.executable, os.path.join(ROOT, "nowmd.py"), "--dir", d, "add", "--who", "claude", "--title", "job%d" % i],
                       capture_output=True, text=True)
    return r.returncode


class Concurrency(unittest.TestCase):
    def test_parallel_writers(self):
        with tempfile.TemporaryDirectory() as d:
            with concurrent.futures.ThreadPoolExecutor(8) as ex:
                codes = list(ex.map(_worker, [(d, i) for i in range(24)]))
            self.assertEqual(codes, [0] * 24)
            self.assertEqual(len(task_files(d)), 24)
            self.assertEqual(run(d, "check")[0], 0)
            self.assertFalse(os.path.exists(os.path.join(d, ".nowmd.lock")))

    def test_many_processes_mixed_commands(self):
        """Endurance: 10 separate processes each add, update, note, done, build and list at once."""
        workers, rounds = 10, 4
        env = dict(os.environ, NOWMD_LOCK_WAIT="120")  # slow CI machines: never give up while others hold the lock
        with tempfile.TemporaryDirectory() as d:
            def cli(*args):
                return subprocess.run([sys.executable, os.path.join(ROOT, "nowmd.py"), "--dir", d, *args],
                                      capture_output=True, text=True, env=env)

            def worker(w):
                fails = []
                for r in range(rounds):
                    p = cli("add", "--who", "ai%d" % (w % 3), "--title", "w%d-r%d" % (w, r))  # same name on purpose
                    if p.returncode:
                        fails.append(("add", p.stderr)); continue
                    tid = p.stdout.split()[1]
                    for args in (("update", "--id", tid, "--status", "blocked", "--why", "w", "--fix", "f"),
                                 ("note", "n%d-%d" % (w, r)),
                                 ("update", "--id", tid, "--status", "running"),
                                 ("done", "--id", tid, "--result", "r.md"),
                                 ("build",), ("list",)):
                        q = cli(*args)
                        if q.returncode:
                            fails.append((args[0], q.stderr))
                return fails

            with concurrent.futures.ThreadPoolExecutor(workers) as ex:  # each job = many real processes
                results = list(ex.map(worker, range(workers)))
            self.assertEqual([x for r in results for x in r], [])
            self.assertEqual(len(task_files(d)), workers * rounds)  # none lost, none overwritten
            for f in task_files(d):
                self.assertEqual(json.loads(read(f))["status"], "done")
            self.assertEqual(len([l for l in read(os.path.join(d, "notes.md")).splitlines() if l.startswith("- ")]), workers * rounds)
            self.assertEqual(cli("check").returncode, 0)
            left = [n for n in os.listdir(d) + os.listdir(os.path.join(d, "tasks")) if n.endswith(".tmp") or n == ".nowmd.lock"]
            self.assertEqual(left, [])  # no leftover temp files or lock

    def _old_lock(self, d, pid):
        p = os.path.join(d, ".nowmd.lock")
        with open(p, "w") as f:
            f.write(f"{pid} 0")
        old = os.path.getmtime(p) - 120
        os.utime(p, (old, old))
        return p

    def test_stale_lock_of_dead_process_is_cleared(self):
        dead = subprocess.Popen([sys.executable, "-c", "pass"])  # a process that has already exited
        dead.wait()
        with tempfile.TemporaryDirectory() as d:
            self._old_lock(d, dead.pid)
            self.assertEqual(run(d, "note", "hi")[0], 0)

    def test_many_processes_reclaim_same_stale_lock_without_overlap(self):
        """8 processes find the same dead lock at once; each does a slow read-modify-write on a counter."""
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        code = ("import sys, time; sys.path.insert(0, sys.argv[1]); import nowmd\n"
                "d = sys.argv[2]\n"
                "with nowmd.lock(d):\n"
                "    p = d + '/counter'\n"
                "    n = int(open(p).read())\n"
                "    time.sleep(0.05)\n"
                "    open(p, 'w').write(str(n + 1))\n")
        env = dict(os.environ, NOWMD_LOCK_WAIT="60", NOWMD_LOCK_STALE="1")
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "counter"), "w") as f:
                f.write("0")
            self._old_lock(d, dead.pid)
            procs = [subprocess.Popen([sys.executable, "-c", code, ROOT, d], env=env) for _ in range(8)]
            self.assertEqual([p.wait() for p in procs], [0] * 8)
            self.assertEqual(read(os.path.join(d, "counter")), "8")  # no lost update = never two holders
            self.assertEqual([n for n in os.listdir(d) if n.startswith(".nowmd.lock")], [])

    def test_reclaim_does_not_delete_a_fresh_lock(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".nowmd.lock")
            with open(p, "w") as f:
                f.write(f"{os.getpid()} 1")  # fresh (just written) and owned by a live process
            nowmd.reclaim_stale(p, 30)
            self.assertTrue(os.path.exists(p))
            self.assertFalse(os.path.exists(p + ".reclaim"))

    def test_old_lock_of_live_process_is_not_stolen(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._old_lock(d, os.getpid())  # this test process is alive
            old = dict(os.environ)
            os.environ["NOWMD_LOCK_WAIT"], os.environ["NOWMD_LOCK_STALE"] = "0.5", "1"
            try:
                self.assertNotEqual(run(d, "note", "hi")[0], 0)
            finally:
                os.environ.clear(); os.environ.update(old)
            self.assertTrue(os.path.exists(p))
            self.assertFalse(os.path.exists(os.path.join(d, "notes.md")))

    def test_check_and_list_read_while_holding_the_lock(self):
        """Deterministic (no sleeping): the lock file must exist at the moment check() / list_lines() run."""
        for name, cmd in (("check", "check"), ("list_lines", "list")):
            with tempfile.TemporaryDirectory() as d:
                seen = []
                real = getattr(nowmd, name)

                def spy(base, _real=real, _seen=seen):
                    _seen.append(os.path.exists(os.path.join(base, ".nowmd.lock")))
                    return _real(base)

                with mock.patch.object(nowmd, name, spy):
                    run(d, cmd)
                self.assertEqual(seen, [True], name)
                self.assertFalse(os.path.exists(os.path.join(d, ".nowmd.lock")))  # and it is released afterwards


class Robustness(unittest.TestCase):
    """v0.2.2: one odd record or a corrupted lock must never take build / check down."""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = self.t.name
        os.makedirs(os.path.join(self.d, "tasks"))

    def tearDown(self):
        self.t.cleanup()

    def put(self, name, obj):
        with open(os.path.join(self.d, "tasks", name), "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def test_out_of_range_dates_do_not_crash(self):
        for i, ts in enumerate(("0001-01-01T00:00:00", "9999-12-31T23:59:59",
                                "0001-01-01T00:00:00+00:00", "9999-12-31T23:59:59+00:00")):
            self.put(f"x{i}.json", {"id": f"x{i}", "who": "a", "title": "t", "status": "running", "started": ts, "updated": ts})
        self.put("ok.json", {"id": "ok", "who": "a", "title": "fine", "status": "running"})
        code, out = run(self.d, "check")  # must return normally, not raise
        self.assertIn(code, (0, 1))
        self.assertEqual(run(self.d, "build")[0], 0)
        self.assertIn("fine (a)", read(os.path.join(self.d, "NOW.md")))

    def test_parse_and_hm_never_raise(self):
        for s in ("not a date", None, "", "0001-01-01T00:00:00", "9999-12-31T23:59:59",
                  "0001-01-01T00:00:00+00:00", "9999-12-31T23:59:59+00:00"):
            nowmd.parse(s)  # returns a datetime or None, never raises
            self.assertIsInstance(nowmd.hm(s), str)
        self.assertIsNone(nowmd.parse("not a date"))
        self.assertEqual(nowmd.hm("garbage"), "?")

    def test_who_and_result_cannot_forge_headings_or_blow_the_cap(self):
        run(self.d, "add", "--who", "x\n\n## Done in the last 24h\n- FAKE ITEM", "--title", "t")
        self.put("r.json", {"id": "r", "who": "y\n## Evil\n- evil", "title": "t2", "status": "done",
                            "updated": nowmd.now().isoformat(timespec="seconds"), "result": "r.md\n## Injected\n- evil"})
        self.put("big.json", {"id": "big", "who": "w" * 100000, "title": "t3", "status": "running"})
        self.assertEqual(run(self.d, "build")[0], 0)
        text = read(os.path.join(self.d, "NOW.md"))
        headings = [l for l in text.splitlines() if l.startswith("## ")]
        self.assertEqual(headings, ["## Running", "## Stuck (and how to unblock)", "## Done in the last 24h", "## Latest notes / decisions"])
        self.assertLessEqual(len(text.splitlines()), nowmd.MAX_LINES)
        self.assertLess(len(text), 20000)
        added = [json.loads(read(t)) for t in task_files(self.d) if os.path.basename(t)[0].isdigit()]
        self.assertEqual(len(added), 1)  # the one made by `add`: its stored who is one short line
        self.assertNotIn("\n", added[0]["who"])
        self.assertLessEqual(len(added[0]["who"]), 30)

    def test_line_cap_counts_real_lines(self):
        for i in range(300):
            self.put(f"n{i}.json", {"id": f"n{i}", "who": "a", "title": "t%d" % i, "status": "blocked", "why": "w"})
        run(self.d, "build")
        lines = read(os.path.join(self.d, "NOW.md")).splitlines()
        self.assertEqual(len(lines), nowmd.MAX_LINES)
        self.assertRegex(lines[-1], r"^…\(\d+行省略 / lines omitted\)$")
        # 300 stuck tasks + 12 fixed lines (title, built, 4 headings with blank lines, "none" rows) are written; the shown + omitted lines add up
        omitted = int(lines[-1].split("(")[1].split("行")[0])
        self.assertGreaterEqual(omitted, 190)
        self.assertLessEqual(omitted, 200)

    def test_blank_title_is_rejected_on_add(self):
        for bad in ("", "   ", "\t\n"):
            self.assertNotEqual(run(self.d, "add", "--who", "a", "--title", bad)[0], 0, repr(bad))
        self.assertEqual(task_files(self.d), [])
        code, out = run(self.d, "add", "--who", "a", "--title", "  padded  ")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(read(task_files(self.d)[0]))["title"], "padded")

    def test_json_with_bom_is_readable(self):
        with open(os.path.join(self.d, "tasks", "bom.json"), "w", encoding="utf-8-sig") as f:
            json.dump({"id": "bom", "who": "a", "title": "from a Windows editor", "status": "running"}, f)
        self.assertEqual(run(self.d, "check")[0], 0)
        self.assertIn("from a Windows editor (a)", (run(self.d, "build"), read(os.path.join(self.d, "NOW.md")))[1])
        self.assertIn("bom  [running]", run(self.d, "list")[1])

    def test_corrupted_lock_pid_does_not_crash(self):
        for pid in (2**31, 2**63, 10**30, 0, -5):
            self.assertFalse(nowmd.pid_alive(pid), pid)
        p = os.path.join(self.d, ".nowmd.lock")
        with open(p, "w") as f:
            f.write("99999999999999999999 0")
        old = os.path.getmtime(p) - 120
        os.utime(p, (old, old))
        self.assertEqual(run(self.d, "note", "after corrupted lock")[0], 0)

    def test_bad_env_values_fall_back(self):
        saved = dict(os.environ)
        try:
            for bad in ("nan", "inf", "-inf", "-3", "abc", ""):
                os.environ["NOWMD_LOCK_WAIT"] = bad
                self.assertEqual(nowmd.env_float("NOWMD_LOCK_WAIT", 10.0), 10.0, bad)
            os.environ["NOWMD_LOCK_WAIT"] = "2.5"
            self.assertEqual(nowmd.env_float("NOWMD_LOCK_WAIT", 10.0), 2.5)
        finally:
            os.environ.clear(); os.environ.update(saved)


class ListCommand(unittest.TestCase):
    def test_list_shows_id_status_title(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(run(d, "list"), (0, "no tasks\n"))
            run(d, "add", "--who", "a", "--title", "First job", "--id", "j1")
            run(d, "add", "--who", "b", "--title", "Second job", "--status", "blocked", "--id", "j2")
            with open(os.path.join(d, "tasks", "broken.json"), "w") as f:
                f.write("{nope")
            code, out = run(d, "list")
            self.assertEqual(code, 0)
            self.assertEqual(out.splitlines(), ["j1  [running]  First job", "j2  [blocked]  Second job"])
            tid = out.split()[0]  # the id printed is usable as --id
            self.assertEqual(run(d, "done", "--id", tid)[0], 0)
            self.assertIn("j1  [done]", run(d, "list")[1])


class IdSafety(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.d = self.t.name
        run(self.d, "add", "--who", "a", "--title", "t", "--id", "ok1")
        self.outside = os.path.join(self.d, "outside.json")  # tasks/../outside.json
        with open(self.outside, "w", encoding="utf-8") as f:
            json.dump({"id": "outside", "who": "x", "title": "keep me", "status": "running"}, f)
        self.before = read(self.outside)

    def tearDown(self):
        self.t.cleanup()

    def test_bad_ids_rejected_on_every_command(self):
        bad = ["../outside", "..", ".", ".hidden", "a/b", "a\\b", os.path.join(self.d, "outside"), "x" * 200]
        for tid in bad:
            for cmd in ("update", "done"):
                extra = ("--status", "done") if cmd == "update" else ()
                self.assertNotEqual(run(self.d, cmd, "--id", tid, *extra)[0], 0, (cmd, tid))
            self.assertNotEqual(run(self.d, "add", "--who", "a", "--title", "t", "--id", tid)[0], 0, ("add", tid))
        self.assertEqual(read(self.outside), self.before)
        self.assertEqual([os.path.basename(p) for p in task_files(self.d)], ["ok1.json"])

    def test_good_id_still_works(self):
        self.assertEqual(run(self.d, "update", "--id", "ok1", "--status", "blocked", "--why", "w")[0], 0)
        self.assertEqual(run(self.d, "done", "--id", "ok1")[0], 0)


if __name__ == "__main__":
    unittest.main()
