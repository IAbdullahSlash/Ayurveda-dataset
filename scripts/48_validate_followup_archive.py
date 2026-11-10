#!/usr/bin/env python3
"""Exercise a fresh local archive without claiming an upstream rebuild or clinical test."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=ROOT / 'release/AyurKB_v1.3.zip')
    parser.add_argument('--junit', type=Path, required=True)
    parser.add_argument('--model', type=Path, help='Optional verified local base-model directory; not bundled')
    parser.add_argument('--environment-evidence', type=Path, help='Optional clean-install receipt to bind to this interpreter, dependency files and test run')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/followup_archive_validation.json')
    args = parser.parse_args()
    tests = ET.parse(args.junit).getroot().findall('.//testcase')
    if not tests or any(case.find('failure') is not None or case.find('error') is not None for case in tests):
        raise ValueError('A successful test run is required')
    skipped = sum(case.find('skipped') is not None for case in tests)
    if skipped == len(tests):
        raise ValueError('No passing tests supplied')
    hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted((ROOT / 'data/processed').glob('*.csv'))}
    dependency_hashes = {name:digest(ROOT / name) for name in ['requirements.txt', 'requirements.cpu-py313.lock']}
    if args.environment_evidence:
        receipt = json.loads(args.environment_evidence.read_text(encoding="utf-8"))
        recorded = receipt['environment']
        current_versions = {d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata.get('Name')}
        if (Path(recorded['executable']).absolute() != Path(sys.executable).absolute()
                or recorded['all_installed_versions'] != current_versions
                or not recorded['isolated'] or recorded['external_site_packages'] or recorded['mismatched_pins']
                or receipt['requirements_sha256'] != dependency_hashes['requirements.txt']
                or receipt['transitive_version_lock']['sha256'] != dependency_hashes['requirements.cpu-py313.lock']
                or receipt['tests']['junit_sha256'] != digest(args.junit)):
            raise ValueError('Clean-install receipt does not match current interpreter/dependencies/tests')
    commands = []
    with tempfile.TemporaryDirectory(prefix='ayurkb-followup-archive-') as temp:
        target = Path(temp)
        with zipfile.ZipFile(args.archive) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP integrity failure')
            for name, expected in hashes.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ValueError('Stale archive CSV: ' + name)
            for name, expected in dependency_hashes.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                    raise ValueError('Missing or stale dependency specification: ' + name)
            archive.extractall(target)
        descriptor = json.loads((target / 'release/datapackage.json').read_text(encoding="utf-8"))
        for resource in descriptor['resources']:
            if not (target / 'release' / resource['path']).is_file():
                raise ValueError('Unresolved descriptor resource')
        # sqlite3's own context manager commits but does not close; an open file blocks cleanup on Windows
        with closing(sqlite3.connect(target / 'release/ayurkb.sqlite')) as connection:
            if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite integrity failure')
            rows = connection.execute('SELECT herb_id,disease_id,mapping_status FROM herb_indication').fetchall()
            allowed = {(h, d) for h, d, state in rows if d and state in {'source_matched_unreviewed', 'alias_reviewed'}}
            if any(d for _, d, state in rows if state in {'quarantined', 'candidate_review_pending', 'unmatched'}):
                raise ValueError('Inactive indication contains an active target')
            evidence = connection.execute('SELECT herb_id,disease_id FROM herb_indication_evidence').fetchall()
            if not set(evidence) <= allowed:
                raise ValueError('Unsupported indication evidence in archive')
            states = dict(connection.execute('SELECT safety_assessment_status,COUNT(*) FROM herbs GROUP BY safety_assessment_status'))
            if '' in states or not set(states) <= {'unassessed', 'review_pending', 'assessed'}:
                raise ValueError('Missing or unknown safety assessment state')
            material_categories = dict(connection.execute('SELECT material_type,COUNT(*) FROM herbs GROUP BY material_type'))
            if not set(material_categories) <= {'botanical_taxon_linked', 'non_botanical_material', 'identity_unresolved'}:
                raise ValueError('Missing or unknown material category')
            if connection.execute("SELECT COUNT(*) FROM herbs WHERE material_type='non_botanical_material' AND gbif_key!=''").fetchone()[0]:
                raise ValueError('Non-botanical category contradicts stored plant taxon link')
            if connection.execute("SELECT COUNT(*) FROM formulation_ingredients i JOIN herbs h ON i.herb_id=h.herb_id WHERE h.material_type='non_botanical_material' AND i.ingredient_type!='mineral/animal/other'").fetchone()[0]:
                raise ValueError('Non-botanical ingredient is still classified as an herb')
        if args.model:
            model = args.model.resolve()
            (target / 'models/multilingual-e5-small').symlink_to(model, target_is_directory=True)
        for language, symptoms in [('en', 'fever, cough'), ('hi', 'बुखार, खाँसी')]:
            command = [sys.executable, '-I', str(target / 'examples/expert_system_demo.py'),
                       '--lang', language, '--symptoms', symptoms]
            if not args.model:
                command.append('--no-semantic')
            environment = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
            result = subprocess.run(command, cwd=tempfile.gettempdir(), env=environment, capture_output=True, text=True, encoding="utf-8", timeout=120)
            if result.returncode:
                raise ValueError('Extracted demo failed: ' + result.stderr[-2000:])
            if 'decision support for a qualified practitioner' not in result.stdout:
                raise ValueError('Expected scoped demo output missing')
            commands.append(dict(language=language, status='passed', mode='base semantic' if args.model else 'lexical'))
    report = dict(archive_sha256=digest(args.archive), csv_sha256=hashes, dependency_sha256=dependency_hashes,
        zip_integrity='passed', descriptor_resources=len(descriptor['resources']), sqlite_integrity='passed',
        unsupported_indication_evidence=0, safety_states=states, material_categories=material_categories, extracted_demos=commands,
        test_run=dict(passed=len(tests)-skipped, skipped=skipped, failed=0, errors=0, junit_sha256=digest(args.junit)),
        dependency_scope='existing pinned Python environment; no clean dependency install claimed',
        model_scope='verified base weights supplied locally; not bundled' if args.model else 'lexical only; no model used',
        model_sha256=digest(args.model / 'model.safetensors') if args.model else None,
        upstream_rebuild_established=False, external_clinical_validation=False)
    if args.environment_evidence:
        report['dependency_scope'] = 'Clean-install receipt matches this isolated interpreter, all installed versions, dependency specifications and JUnit run; weights/data supplied separately.'
        report['clean_install_receipt_sha256'] = digest(args.environment_evidence)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding="utf-8")
    print(json.dumps({key:value for key,value in report.items() if key != 'csv_sha256'}, indent=2))


if __name__ == '__main__':
    main()
