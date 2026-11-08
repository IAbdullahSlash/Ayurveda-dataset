"""
Character n-gram language model for restoring lost IAST diacritics ('mah?bh?ta' -> 'mahābhūta').

The NAMASTE SAT database replaced every non-ASCII IAST letter by '?'.  Exact vocabulary lookup
repairs most tokens; for the rest we score candidate fillings with a smoothed character 4-gram
model trained on clean IAST words and keep the best one via beam search.  `evaluate()` measures
accuracy on held-out clean words that are corrupted the same way the source was.
"""
import math, random
from collections import Counter, defaultdict

LOST = ["ā", "ī", "ū", "ṛ", "ṝ", "ḷ", "ṅ", "ñ", "ṭ", "ḍ", "ṇ", "ś", "ṣ", "ṃ", "ḥ"]

class CharNgram:
    def __init__(self, n=4, k=0.05):
        self.n, self.k = n, k
        self.counts = defaultdict(Counter)
        self.vocab = set()

    def fit(self, words):
        for w in words:
            s = "^" * (self.n - 1) + w + "$"
            for i in range(self.n - 1, len(s)):
                for L in range(self.n):                # every history length 0..n-1 (for back-off)
                    self.counts[s[i - L:i]][s[i]] += 1
                self.vocab.add(s[i])
        self.V = len(self.vocab)
        self.tot = {h: sum(c.values()) for h, c in self.counts.items()}
        return self

    def logp(self, hist, ch):
        # interpolated back-off over shorter histories (simple, robust)
        lp, lam = 0.0, [0.6, 0.25, 0.1, 0.05]
        p = 0.0
        for j, l in enumerate(lam[: self.n]):
            h = hist[j:] if j < len(hist) else ""
            c = self.counts.get(h)
            if c:
                p += l * (c[ch] + self.k) / (self.tot[h] + self.k * self.V)
            else:
                p += l / self.V
        return math.log(p)

    def score(self, w):
        s = "^" * (self.n - 1) + w + "$"
        return sum(self.logp(s[i - self.n + 1:i], s[i]) for i in range(self.n - 1, len(s)))

    def restore(self, tok, beam=64):
        """fill each '?' with a lost IAST letter; returns (best, margin_logprob)."""
        beams = [("", 0.0)]
        pad = "^" * (self.n - 1)
        for ch in tok + "$":
            nxt = []
            opts = LOST if ch == "?" else [ch]
            for pre, sc in beams:
                hist = (pad + pre)[-(self.n - 1):]
                for o in opts:
                    nxt.append((pre + o if o != "$" else pre, sc + self.logp(hist, o)))
            nxt.sort(key=lambda x: -x[1])
            beams = nxt[:beam]
        best = beams[0]
        margin = best[1] - beams[1][1] if len(beams) > 1 else 99.0
        return best[0], margin

def corrupt(w):
    return "".join("?" if c in LOST else c for c in w)

def evaluate(words, n_test=1500, seed=0):
    words = [w for w in sorted(set(words)) if any(c in LOST for c in w) and len(w) >= 4]   # sorted: reproducible split
    rnd = random.Random(seed)
    rnd.shuffle(words)
    test, train = words[:n_test], words[n_test:]
    m = CharNgram().fit(train)
    res = [(m.restore(corrupt(w)), w) for w in test]
    ok = [r[0] == w for r, w in res]
    margins = [r[1] for r, w in res]
    curve = {}
    for thr in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
        sel = [o for o, mg in zip(ok, margins) if mg >= thr]
        curve[str(thr)] = dict(coverage=round(len(sel) / len(ok), 4),
                               precision=round(sum(sel) / max(1, len(sel)), 4))
    return dict(n_train=len(train), n_test=len(test), exact_word_accuracy=round(sum(ok) / len(ok), 4),
                precision_coverage_by_margin=curve)
