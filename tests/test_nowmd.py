"""Run: python3 -m unittest discover -s tests -v   (from the repo root)"""
import concurrent.futures, contextlib, glob, io, json, os, subprocess, sys, tempfile, unittest

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

    def test_stale_lock_is_cleared(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".nowmd.lock")
            with open(p, "w") as f:
                f.write("999999")
            old = os.path.getmtime(p) - 120
            os.utime(p, (old, old))
            self.assertEqual(run(d, "note", "hi")[0], 0)


if __name__ == "__main__":
    unittest.main()
