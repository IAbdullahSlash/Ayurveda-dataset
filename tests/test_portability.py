"""Guard against Windows-only failures that have reappeared in new pipeline code.

1. Text file I/O must name its encoding. Without it Python uses the platform code page
   (e.g. cp1252 or cp1256 on Windows), which cannot read or write Devanagari and IAST.
2. Numbered scripts that import lib/ must add their own folder to sys.path, because
   run_all.sh runs them with `python -I`, which leaves the script folder off the path.
3. Paths written into manifests and reports must use forward slashes (`.as_posix()`),
   so the output is the same whichever OS produced it.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CODE_DIRS = ("scripts", "tests", "examples")


def python_files(root=ROOT):
    return sorted(p for d in CODE_DIRS for p in (root / d).rglob("*.py"))


def _has_kw(call, name):
    return any(k.arg == name for k in call.keywords)


def _mode(call, position):
    """The literal mode string of an open() call, or None when absent or not a literal."""
    for k in call.keywords:
        if k.arg == "mode":
            return k.value.value if isinstance(k.value, ast.Constant) and isinstance(k.value.value, str) else ""
    if len(call.args) > position:
        a = call.args[position]
        return a.value if isinstance(a, ast.Constant) and isinstance(a.value, str) else ""
    return None


def encoding_problems(path):
    """Calls that read or write text without an explicit encoding."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _has_kw(node, "encoding"):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "read_text" and not node.args:
            found.append((node.lineno, ".read_text() without encoding"))
        elif isinstance(f, ast.Attribute) and f.attr == "write_text" and len(node.args) < 2:
            found.append((node.lineno, ".write_text() without encoding"))
        elif isinstance(f, ast.Name) and f.id == "open":
            mode = _mode(node, 1)
            if mode is None or (mode and "b" not in mode):
                found.append((node.lineno, "open() in text mode without encoding"))
        elif isinstance(f, ast.Attribute) and f.attr == "open":
            # Path.open(mode); other .open() calls (zipfile, tarfile) take a member name first
            mode = _mode(node, 0)
            if (not node.args and not node.keywords) or (mode and "b" not in mode and set(mode) <= set("rwxat+")):
                found.append((node.lineno, "Path.open() in text mode without encoding"))
    return found


def path_problems(path):
    """str(x.relative_to(...)) writes backslashes on Windows; use .as_posix()."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str" and node.args
                and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "relative_to"
                        for n in ast.walk(node.args[0]))):
            found.append((node.lineno, "str(path.relative_to(...)); use .relative_to(...).as_posix()"))
    return found


def isolated_import_problem(path):
    """A numbered script that imports lib/ before putting its folder on sys.path."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    first_lib, first_insert = None, None
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "lib":
            first_lib = line if first_lib is None else min(first_lib, line)
        elif isinstance(node, ast.Import) and any(a.name.split(".")[0] == "lib" for a in node.names):
            first_lib = line if first_lib is None else min(first_lib, line)
        elif (isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) == "import_module"
              and node.args and isinstance(node.args[0], ast.Constant) and str(node.args[0].value)[:1].isdigit()):
            # import_module("10_crosslingual") loads a sibling script, which also needs the script folder on sys.path
            first_lib = line if first_lib is None else min(first_lib, line)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "insert"
              and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "path"):
            first_insert = line if first_insert is None else min(first_insert, line)
    if first_lib is not None and (first_insert is None or first_insert > first_lib):
        return first_lib
    return None


def sqlite_problems(path):
    """`with sqlite3.connect(...) as c:` commits but never closes; Windows then cannot delete or replace the file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                f = item.context_expr
                if (isinstance(f, ast.Call) and isinstance(f.func, ast.Attribute) and f.func.attr == "connect"
                        and isinstance(f.func.value, ast.Name) and f.func.value.id == "sqlite3"):
                    found.append((node.lineno, "with sqlite3.connect(...) leaves the file open; wrap it in contextlib.closing()"))
    return found


def _report(problems):
    return "\n".join(f"  {p.relative_to(ROOT).as_posix()}:{line}  {msg}" for p, line, msg in problems)


def test_text_io_names_its_encoding():
    problems = [(p, line, msg) for p in python_files() for line, msg in encoding_problems(p)]
    assert not problems, "Pass encoding='utf-8' (Windows defaults to a legacy code page):\n" + _report(problems)


def test_manifest_paths_use_forward_slashes():
    problems = [(p, line, msg) for p in python_files() for line, msg in path_problems(p)]
    assert not problems, "Paths written to files must not depend on the OS:\n" + _report(problems)


def test_sqlite_connections_are_closed():
    problems = [(p, line, msg) for p in python_files() for line, msg in sqlite_problems(p)]
    assert not problems, "An open SQLite file cannot be deleted on Windows:\n" + _report(problems)


@pytest.mark.parametrize("source,flagged", [
    ("import sqlite3\nwith sqlite3.connect('a.db') as c:\n    c.execute('select 1')\n", True),
    ("import sqlite3\nfrom contextlib import closing\nwith closing(sqlite3.connect('a.db')) as c:\n    c.execute('select 1')\n", False),
])
def test_checker_catches_unclosed_sqlite(tmp_path, source, flagged):
    f = tmp_path / "sample.py"
    f.write_text(source, encoding="utf-8")
    assert bool(sqlite_problems(f)) == flagged


def test_numbered_scripts_import_lib_under_isolated_mode():
    problems = []
    for p in sorted((ROOT / "scripts").glob("[0-9]*.py")):
        line = isolated_import_problem(p)
        if line:
            problems.append((p, line, "imports lib/ or a sibling script without sys.path.insert(0, script folder) first"))
    assert not problems, "run_all.sh runs stages with `python -I`, which omits the script folder:\n" + _report(problems)


BAD = '''
import json
from pathlib import Path
from lib.keys import skeleton
p = Path("x.json")
data = json.loads(p.read_text())
p.write_text(json.dumps(data))
with open("y.csv") as f: pass
with open("z.csv", "w") as f: pass
with p.open() as f: pass
with p.open("a") as f: pass
name = str(p.relative_to(Path(".")))
'''

GOOD = '''
import json, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.keys import skeleton
p = Path("x.json")
data = json.loads(p.read_text(encoding="utf-8"))
p.write_text(json.dumps(data), encoding="utf-8")
p.write_text("x", "utf-8")
with open("y.csv", encoding="utf-8") as f: pass
with open("y.bin", "rb") as f: pass
with p.open("wb") as f: pass
with p.open("a", encoding="utf-8") as f: pass
with zipfile.ZipFile("a.zip").open("member.txt") as f: pass
name = p.relative_to(Path(".")).as_posix()
'''


@pytest.mark.parametrize("source,flagged", [
    ("import importlib\nspecs = importlib.import_module('00_get_models')\n", True),
    ("import sys, importlib\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent))\nspecs = importlib.import_module('00_get_models')\n", False),
    ("import importlib\njson = importlib.import_module('json')\n", False),
])
def test_checker_catches_sibling_script_imports(tmp_path, source, flagged):
    f = tmp_path / "39_sample.py"
    f.write_text(source, encoding="utf-8")
    assert (isolated_import_problem(f) is not None) == flagged


@pytest.mark.parametrize("source,expected", [(BAD, 6), (GOOD, 0)])
def test_checker_catches_known_patterns(tmp_path, source, expected):
    """The guard itself must flag every unsafe pattern above and accept the safe ones."""
    f = tmp_path / "10_sample.py"
    f.write_text(source, encoding="utf-8")
    assert len(encoding_problems(f)) == expected
    assert len(path_problems(f)) == (1 if source is BAD else 0)
    assert (isolated_import_problem(f) is not None) == (source is BAD)
