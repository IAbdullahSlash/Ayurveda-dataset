# End-to-end rebuild check, 8 November 2026

`bash run_all.sh` had never been run end to end against the committed data. This records an attempt on Windows 10 with Python 3.13.12, the pinned requirements and the checksum-verified NLLB-200 and multilingual-e5 models.

**Result: not yet verified end to end.** Stages 00, 01 and 02b to 06 (translation) ran; the run stopped before the remaining stages. It found one real bug, now fixed, and showed that the committed data cannot be reproduced exactly from the committed code.

## What happened

| Stage | Outcome |
|---|---|
| 00 models | Downloaded; checksums match the Hugging Face revisions (stage 39). |
| 01 fetch | All sources already present; nothing re-downloaded. Two problems, both fixed: every `retrieved_utc` was rewritten on each run (stage 01 now keeps it while a file's hash is unchanged), and the four Amidha files did not match their recorded hashes on Windows, because git converted their line endings on checkout (`.gitattributes` now stops conversion under `data/raw/`). |
| 02a WHO parse | Not run. It needs Poppler's `pdftotext -bbox-layout`; this machine had the Xpdf build of `pdftotext` (4.00), which lacks that option. The committed parse in `data/interim/who_*.csv` was used instead. |
| 02b NAMASTE parse | **Non-deterministic.** Two runs on identical input disagreed. Fixed in commit `1ccae7a` (see below). |
| 02c–05 | Ran. |
| 06 translation | Translated 351 strings missing from the cache, all caused by the 02b differences. |
| 06 quality check | Stopped by a disk-space watchdog when free space fell to 378 MB while both translation directions were loaded. |

Stages 07 to 55 did not run in this attempt.

## The stage 02b bug

The diacritic repair added spelling variants to a counter in set order, which changes with Python's per-run hash seed, and then kept whichever equally frequent candidate came first. Three runs of the fixed code now give byte-identical output with the committed repair counts.

The committed interim parse came from one random order. Regenerating it from the fixed code changes 104 SAT definitions and 61 mahākaṣāya member names. Most changes restore long final vowels that the old run dropped: guḍūca → guḍūcī, punarnava → punarnavā, haridra → haridrā, musta → mustā, sāriva → sārivā. A few are doubtful (bādhanam → bṛṃhaṇam in one definition). Stage 06 needs new translations for the changed text (327 strings).

**The regeneration has not been applied.** It is a data change that needs review of the changed spellings and a full run of stages 02b to 08.

## Second rebuild, 10–11 November 2026

Stages 02b to 22 of `run_all.sh` were run in a separate worktree from the fixed stage 02b, with 02a's committed WHO parse reused (no Poppler), the case-report pool frozen to the 565 committed publications, and the benchmark stages (07, 10, 20, 23, 26) and the stage 06 back-translation check skipped. It took about 2 h 50 min on a 4-core CPU, most of it stage 06 translation (45 min), the stage 11 index (27 min) and the stage 14 full-text downloads (81 min).

- **Bug found and fixed:** stage 25 crashed on any from-scratch build, because its first Hindi correction pass read `diseases.definition_source` before the stage created it. Fixed in v1.3.0 with a regression test.
- **Every stage then completed** and stage 08's integrity checks passed.
- **Not adopted.** Besides the 02b changes (78 term definitions, 19 term names, 34 mahākaṣāya member lists, one herb name, four WHO links), the rebuilt tables also apply the symptom-parser change of 6 November, which stops splitting phrases at "and" and "with". That change awaits two reviewers (`reports/revision_audit/symptom_extraction_changes.csv`, all 211 rows `pending`). Applying it retires 351 NAMASTE symptom IDs, adds 225, removes 335 disease–symptom links, recomposes about 230 Hindi disorder definitions and changes the symptoms of 68 case reports. The committed data therefore keeps the reviewed v1.2 splits, and the regeneration waits for that review.

## To finish the check

1. Install Poppler (so that `pdftotext -bbox-layout` works) and free about 4 GB of disk space beyond the 2.9 GB of model weights.
2. Adjudicate the pending symptom-splitting changes, or make the parser use the released splits until a row is accepted. Then decide whether to regenerate the stage 02b output, after reviewing the 104 + 61 changed spellings.
3. Run `bash run_all.sh` in a separate copy and compare `data/processed/` with the committed tables.

Existing Windows checkouts made before `.gitattributes` was added still hold converted copies of the Amidha files. Restore the exact bytes once with `git show HEAD:<path> > <path>` for each file under `data/raw/amidha_herb_db/`, or re-clone.
