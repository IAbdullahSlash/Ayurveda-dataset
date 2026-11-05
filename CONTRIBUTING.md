# Contributing to AyurKB

Thank you for helping. This guide is for anyone who wants to correct, extend or rebuild the dataset. Read
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for how the pieces fit together, and
[`docs/GLOSSARY.md`](docs/GLOSSARY.md) if Ayurveda or Sanskrit terms are new to you.

The most valuable contribution is **expert review** by qualified Ayurveda practitioners and Hindi speakers
(Review Desk, or `review/AyurKB_expert_review.xlsx`; see the README). Code and data contributions follow the rules
below.

## 1. Set up

```bash
git clone https://github.com/IAbdullahSlash/Ayurveda-dataset.git
cd Ayurveda-dataset
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # pinned versions; Python 3.13
python3 -m pytest -q tests/              # ~20 s; the release-zip check is skipped until scripts/13_package.sh has run
```

You do **not** need the 2.9 GB of models for most work. They are only needed to translate new text (stage 06
`--translate`), for the semantic index and for the embedding experiments. `poppler-utils` is only needed to re-parse
the WHO PDF.

Run pipeline scripts as `python3 -I scripts/NN_name.py` (isolated mode, as `run_all.sh` does).

## 2. Ground rules

1. **Never edit `data/processed/` by hand.** Fix the value where it comes from (a parser, a file in `curation/`, a
   rule) and re-run the stage. Hand edits are lost on the next rebuild and break provenance.
2. **Flag what is not authoritative.** New curated or inferred content gets a `data_origin` / `status` /
   `*_method` value that says so, and goes into its own table or column rather than overwriting source values.
3. **Only use sources with a clear licence.** Add new sources to `docs/SOURCES.md` and `data/processed/sources.csv`
   with their licence. Share-alike (ChEMBL) and third-party article texts (Europe PMC) stay out of git.
4. **Keep stages idempotent and deterministic.** Running a stage twice must give the same files.
5. **Keep diffs minimal.** A change to Hindi glosses should change only the Hindi and method columns of the affected
   rows, not reformat whole tables.

## 3. Common tasks

### Fix a wrong Hindi machine translation

Systematic errors (the same English word mistranslated in many rows) are fixed with rules in
`curation/mt_postedit_rules.csv`, which stage 25 applies to `symptoms.gloss_hi` and `diseases.definition_hi`.

| Column | Meaning |
|---|---|
| `en_regex` | the row's English must match (case-insensitive), e.g. `\bnause` |
| `en_exclude_regex` | skip the row if its English matches this, e.g. `vomit` when replacing उल्टी. Leave it **blank** only when `hi_wrong_regex` is unambiguous on its own |
| `hi_wrong_regex` | the wrong Hindi (regex, case-sensitive). Every match in the cell is replaced |
| `hi_right` | the replacement text |
| `note` | why the rule exists |

How to write good rules:

- **Bare word** (`उल्टी → मतली`): always give an exclusion naming the English words that would make the Hindi word
  correct (vomiting, fever, burning …). Bare-word rules mainly serve short symptom glosses.
- **Long definitions** list many symptoms, so a bare word may be right in one item and wrong in another. Anchor
  the pattern on context instead, e.g. `हृल्लासः \(उल्टी\)` (the Sanskrit word for nausea followed by the wrong gloss),
  and leave the exclusion blank.
- Do not use capture groups `( )` in `hi_wrong_regex`: pandas warns, and the replacement is plain text. Escape
  literal parentheses as `\(` `\)`; lookarounds `(?<=…)`, `(?=…)` are fine.
- Rules run top to bottom on both tables. A replacement must not re-create its own pattern (idempotency).

Then:

```bash
python3 -I scripts/25_fill_missing.py         # applies the rules; updates reports/fill_missing_report.json
python3 -I scripts/25_fill_missing.py         # second run must change nothing
git diff --stat                               # expect: symptoms.csv, diseases.csv, the report
```

Also add the English → Hindi pair to `curation/glossary_en_hi.csv` (columns `en,hi,note`) so future translations get
it right, and add a regression test (see `test_nausea_not_mistranslated` in `tests/test_extensions.py`). Finally
re-run `08_validate_export.py`, which rebuilds `qa_pairs.csv` (its Hindi answers embed the disorder definitions).

Do **not** re-run `06_translate.py --merge` without re-running stage 25 afterwards: `--merge` rewrites every Hindi
column from the translation cache and removes the post-edits.

### Correct a curated record (formulation, safety class, diagnostic method, vocabulary)

Edit the file in `curation/`, cite the classical or standard reference in its reference/note column, then re-run the
pipeline from stage 04 (see the table in `docs/ARCHITECTURE.md` §5). Formulations must be checked against the
Ayurvedic Formulary of India.

### Fix a botanical name

Add a row to `curation/taxonomy_overrides.csv` with the reason, then re-run from stage 03. Ambiguous synonyms are
left unresolved on purpose; don't guess.

### Add a table or column

Add it in the stage that owns the data, describe it in `TABLE_DOC` / `COL_DOC` in `scripts/09_docs.py` and re-run `09`,
add tests for keys and references, and add it to `release/datapackage.json` by re-running `08`.

### Add a test

Tests live in `tests/test_ayurkb.py` (core tables) and `tests/test_extensions.py` (stages 14–26). Tests for files
built from the network or from models use `@need("table")` or `pytest.skip` so a fresh clone still passes. When the
number of tests changes, update the badge and the two "automated checks" lines in `README.md` and the counts in
`release/report.html` (`scripts/12_report.py` regenerates the report, but it counts the tests in your environment,
where the release-zip check may be skipped).

## 4. Before you commit

- [ ] `python3 -m pytest -q tests/` passes.
- [ ] `git diff --stat` shows only the files you meant to change. For table changes, compare against `HEAD`
      column by column (only the intended columns and rows differ).
- [ ] The stage you changed gives identical output when run twice.
- [ ] Counts quoted in `README.md`, `docs/DATASHEET.md` and `release/report.html` are still right.
- [ ] Nothing that must stay out of git is staged (see `.gitignore`: models, parquet copies, SQLite, embeddings,
      ChEMBL data, Europe PMC texts, returned review workbooks).

## 5. Pitfalls

- **pandas 3 strings.** Text columns are read as the `str` dtype, not `object`, so `df[c].dtype == object` is
  `False` for them. Use `pd.api.types.is_string_dtype`.
- **Always `keep_default_na=False`.** Otherwise empty cells become NaN and words like *na* may too.
- **Composed definitions repeat symptom glosses.** A wrong symptom gloss also appears inside every disorder
  definition that lists that symptom; fix both (the post-edit rules cover both tables).
- **QE flags don't catch everything.** A fluent but wrong word (nausea → "fever") has no flag. Review by meaning,
  not only by flags.
- **Run order matters.** Stage 25 runs after 06, and stage 08 runs after 25 (see `run_all.sh`).
- **`release/report.html` and the README tables are generated** by `12_report.py`; keep hand edits there to counts.

## 6. Commits and pull requests

- Write the commit subject in the imperative ("Fix …", "Add …"), under ~72 characters. In the body, say why,
  what changed, how it was verified, and what was deliberately left out.
- Keep data regeneration in the same commit as the code or curation change that caused it.
- Open a pull request against `main` and describe the verification you did. Report issues (wrong mappings, bad
  translations, licence questions) on GitHub with the record ids involved.

By contributing you agree that your contributions are licensed under the project's licence (CC BY-NC-SA 4.0 for
the combined release; curated files CC BY 4.0).
