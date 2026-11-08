"""Stage 02b's diacritic repair must give the same answer on every run (it once depended on set order)."""
import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
parse = importlib.import_module("02b_parse_namaste")


def test_equal_counts_prefer_the_diacritic_spelling():
    """'majj?' matches both majja and majjā once each; the '?' replaced a diacritic letter, so majjā wins."""
    _, by_len = parse.build_vocab(["majjā majja"])
    assert parse.repair_token("majj?", by_len, {}) == "majjā"


def test_repair_is_independent_of_hash_seed():
    """Run the same repair under different PYTHONHASHSEED values; set iteration order must not change the result."""
    code = ("import sys; sys.path.insert(0, 'scripts'); import importlib; p = importlib.import_module('02b_parse_namaste'); "
            "_, b = p.build_vocab(['dhamanī dhamana kalā kala mahāmedā mahāmeda']); "
            "print([p.repair_token(t, b, {}) for t in ['dhaman?', 'kal?', 'mah?med?']])")
    outputs = set()
    for seed in ("0", "1", "12345"):
        env = {**__import__("os").environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"}
        outputs.add(subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                                   encoding="utf-8", check=True).stdout.strip())
    assert len(outputs) == 1, outputs
