# Known issues and open work

What is known to be wrong, stale or unfinished in AyurKB v1.2, with where to start. If you fix an item, remove it
here in the same commit. General limitations of the dataset (curated layers, synthetic cohort, evidence counts)
are in the [datasheet](DATASHEET.md#6-known-limitations); this page is the working list.

## Data quality

### Hindi machine translations outside the post-edit step

Stage 25 post-edits only `symptoms.gloss_hi` and `diseases.definition_hi`. The nausea fix (मतली) therefore did not
reach:

- **`terminology.csv`**: 15 WHO definitions still render "nausea" wrongly, e.g. "nausea/provocation of dosha" as
  "दोष की जलन/प्रोकोशन" (WHO:ITA-5.33.1) or "खाँसी/ दोष का प्रकोप" (WHO:ITA-5.76.5). Find them with rows whose
  `definition_en` matches `\bnause` and whose non-empty `definition_hi` lacks `मतली`. Two WHO definitions
  (WHO:ITA-5.6.7, WHO:ITA-5.10.4) have no Hindi at all.
- **`qa_pairs.csv`**: built by stage 08 after stage 25. Its Hindi disorder-definition answers repeat the old
  definitions of the 59 disorders corrected in commit `70c9bec` until `08_validate_export.py` is re-run.
- **Semantic Hindi search**: `release/embeddings/symptoms_hi` (not in git) embeds `gloss_hi`; rebuild with
  `11_embed_index.py` to pick up corrected glosses.
- **`review/AyurKB_expert_review.xlsx`** and `release/tools/*.html`: rebuild with stages 21 and 22.

Possible approach: extend `postedit()` to `terminology.definition_hi` with phrase rules anchored on the exact wrong
renderings (whole-paragraph translations make bare-word rules risky), then re-run 25 → 08 → 11 → 21 → 22.

### Translation quality in general

- Hindi glosses and definitions are NLLB-200 output. Quality flags mark 572 of 11,081 symptom glosses, 1,101 of
  5,497 translated WHO/SAT definitions (mostly `repetition`) and 617 of 2,015 disorder definitions.
- **Flags miss fluent wrong-word errors.** None of the nausea errors (मतली rendered as बुखार "fever", जलन "burning",
  उल्टी "vomiting", उलझन "confusion") carried a flag. The same kind of error very likely exists for other symptom words.
  A useful check: for each frequent English symptom word, compare the Hindi words its glosses get and look for ones
  that also translate a different symptom.
- At least one translation is degenerate: the WHO definition copied into AYD-00033 ends in a long "ड्ड्ड…"
  repetition.
- Mean back-translation chrF is 52.4 on a 300-string sample (`reports/translation_qe.json`); 55% score ≥ 50.

The `hindi_translations` sheet of the review workbook exists for a Hindi-speaking reviewer.

### Source-data oddities kept as published

- SYM-N00579's English gloss is the typo "nause" (Sanskrit hṛllāsa, nausea). Source text is not corrected in place;
  the Hindi is right and the post-edit rules match `\bnause` on purpose.
- AYD-02311's definition says "decreased digestive fever" (probably "digestive fire").
- Sign lists in WHO definitions mix symptoms with diseases; they are kept as separate, flagged edges
  (`disease_symptom_who`) and not used for ranking.

### Needs expert verification

- All of `curation/` (formulations, diagnostic correspondences, herb safety, glossary, questionnaire, crosswalk),
  the 1,420 doṣa suggestions, inherited symptom profiles and the case-report curation queue
  (`case_report_links` where `in_kb_for_disorder_family` is false).
- Herb properties come from a single community source (Amidha, 344 herbs).

## Tests and tooling

- **`test_no_mojibake` checks nothing under pandas 3.** It only looks at columns with `dtype == object`, but pandas 3
  reads text as the `str` dtype, so 0 columns are checked. The data is currently clean when the check is run
  properly; fix the column selection (`pd.api.types.is_string_dtype`).
- `tests/test_extensions.py::test_release_zip_excludes_article_texts` is skipped on a fresh clone until
  `bash scripts/13_package.sh` builds the zip. `12_report.py` counts passing tests in the current environment, so
  run it after packaging, or correct the count.
- `scripts/12_report.py` hard-codes "e.g. 'stiffness' had been translated as 'bitterness'" as the example of a rule
  fix; most rule fixes are now the nausea rules.

## Roadmap (from the README)

- Collect expert verdicts (Review Desk or workbook) and merge them with `21_review_workbooks.py --merge`.
- Send the permission letters in `docs/permission_requests/` (NAMASTE has no explicit open licence).
- Obtain ethics approval before collecting real Prakṛti questionnaire responses.
- Optionally import a WHO ICTRP / CTRI export with `19_ictrp_import.py`.
