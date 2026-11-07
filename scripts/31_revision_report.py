#!/usr/bin/env python3
"""Generate current revision counts and validation evidence from concrete artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--junit',type=Path,required=True)
    args=parser.parse_args()
    suites=ET.parse(args.junit).getroot()
    cases=suites.findall('.//testcase')
    failed=sum(case.find('failure') is not None for case in cases)
    errors=sum(case.find('error') is not None for case in cases)
    skipped=sum(case.find('skipped') is not None for case in cases)
    if not cases or failed or errors:
        raise SystemExit('Cannot publish passing validation: empty or unsuccessful test run')
    counts={path.stem:len(pd.read_csv(path,keep_default_na=False)) for path in sorted((ROOT/'data/processed').glob('*.csv'))}
    reports=ROOT/'reports/revision_full/REP'
    result={'tests':{'passed':len(cases)-skipped,'skipped':skipped,'failed':failed,'errors':errors,
                     'junit_sha256':hashlib.sha256(args.junit.read_bytes()).hexdigest()},
            'tables':counts,'rows':sum(counts.values()),'benchmarks':{}}
    lines=['# Revision validation','',
           f'Executed test suite: **{len(cases)-skipped} passed, {skipped} skipped, {failed} failed, {errors} errors**.',
           '',f'Current processed data: **{len(counts)} tables, {sum(counts.values()):,} rows**. Rows include links, derived records and synthetic observations; they are not independent patients.',
           '', '## Corrected benchmark results','',
           '| Experiment | Model | Macro-F1 | Scope |','|---|---|---:|---|']
    for path in sorted(reports.glob('*.json')):
        data=json.loads(path.read_text(encoding="utf-8"))
        if 'results' not in data and 'summary' not in data:
            continue
        rows=data.get('results',data.get('summary',[]))
        languages=sorted({row.get('language','') for row in rows})
        result['benchmarks'][path.stem]={'file':path.relative_to(ROOT).as_posix(), 'n':data.get('n')}
        for language in languages:
            eligible=[r for r in rows if r.get('language','')==language and 'macro_f1_mean' in r]
            if not eligible:
                continue
            best=max(eligible,key=lambda r:r['macro_f1_mean'])
            scope='synthetic development CV; 750 final holdout records' if path.stem.startswith('E4') else 'internal CV; not external clinical validation'
            lines.append(f"| {path.stem} {language} | {best['model']} | {best['macro_f1_mean']:.3f} | {scope} |")
    tuning=reports/'E7_tuning.json'
    if tuning.exists():
        lines+=['','## Corrected nested tuning','','| Task | Model | Default macro-F1 | Tuned macro-F1 |','|---|---|---:|---:|']
        for row in json.loads(tuning.read_text(encoding="utf-8"))['results']:
            lines.append(f"| {row['task']} | {row['model']} | {row['default_macro_f1_mean']:.3f} | {row['tuned_macro_f1_mean']:.3f} |")
        lines+=['','Preprocessing is fitted inside both inner and outer folds. Fold-score p-values are descriptive because CV training sets overlap.']
    upgrades=reports/'E2c_plus.json' 
    if upgrades.exists():
        variants=json.loads(upgrades.read_text(encoding="utf-8"))
        lines+=['','## Corrected chemistry comparison','','| Features | Best model | Mean label macro-F1 |','|---|---|---:|']
        for name,rows in variants.items():
            if not isinstance(rows,list) or not rows or not isinstance(rows[0],dict) or 'macro_f1_mean' not in rows[0]:
                continue
            best=max(rows,key=lambda row:row['macro_f1_mean'])
            lines.append(f"| {name} | {best['model']} | {best['macro_f1_mean']:.3f} |")
        result['benchmarks']['E2c_plus']={'file':upgrades.relative_to(ROOT).as_posix(),'n':variants['n_herbs']}
    lines+=['','Results and split manifests are in `reports/revision_full/`. The historical v1.2 reports remain in `reports/ml/` for comparison. E4 reserves a final holdout before model selection; its revised CV denominator differs from the original release.',
            '', 'The E2c chemistry-upgrade report is stored separately as `E2c_plus.json` because it compares feature variants. Embedding-dependent and retrieval results, when present below, use their own recorded source snapshots and candidate scopes.',
            '', 'Benchmark results refer to their frozen input snapshots in `reports/revision_full/`; subsequent language and graph repairs are not a new benchmark rerun.', '', 'Independent clinical review, bilingual adjudication, source-rights decisions and an external test set remain pending. See `REVISION_STATUS.md` and the dedicated review protocols.']
    semantic=ROOT/'reports/revision_semantic'
    retrieval=semantic/'E5b_finetuned_retrieval.json'
    if retrieval.exists():
        data=json.loads(retrieval.read_text(encoding="utf-8"))
        lines+=['','## Full-corpus bilingual retrieval','','| Task / query | Base recall@10 | Fine-tuned recall@10 |','|---|---:|---:|']
        for task in ['diseases','symptoms']:
            for query in ['hindi_headword','hindi_text']:
                before=data['base'][task][query]['recall_at_10'];after=data['finetuned'][task][query]['recall_at_10']
                lines.append(f"| {task} / {query} | {before:.3f} | {after:.3f} |")
        lines+=['',f"Candidate counts: {data['candidate_counts']}. Fixed record-derived queries; this is retrieval evaluation, not independent clinical validation. Old 800-candidate scores are not directly comparable."]
        result['semantic_retrieval']={'file':retrieval.relative_to(ROOT).as_posix(),'candidate_counts':data['candidate_counts']}
    upgrades=semantic/'E1_plus.json'
    if upgrades.exists():
        lines+=['','## Source-stratified embedding upgrades','','| Task / source scope | Rows | TF-IDF macro-F1 | Combined macro-F1 |','|---|---:|---:|---:|']
        for tag,experiment in json.loads(upgrades.read_text(encoding="utf-8")).items():
            baseline=experiment['results']['TF-IDF + LR (stage 07)']['macro_f1_mean']
            combined=experiment['results']['TF-IDF + e5 + LR']['macro_f1_mean']
            lines.append(f"| {tag} | {experiment['n']} | {baseline:.3f} | {combined:.3f} |")
        result['embedding_upgrades']={'file':upgrades.relative_to(ROOT).as_posix()}
    (ROOT/'reports/revision_validation_summary.json').write_text(json.dumps(result,indent=2)+'\n', encoding="utf-8")
    (ROOT/'docs/REVISION_VALIDATION.md').write_text('\n'.join(lines)+'\n', encoding="utf-8")
if __name__=='__main__':
    main()
