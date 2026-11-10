#!/usr/bin/env python3
"""Record isolated interpreter/dependency and executed JUnit evidence without importing host packages."""
import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''
import importlib.metadata as metadata,json,site,sys,platform
from pathlib import Path
from packaging.specifiers import SpecifierSet
pins=json.loads(sys.stdin.read())
versions={name:metadata.version(name) for name in pins}
all_versions={dist.metadata['Name']:dist.version for dist in metadata.distributions() if dist.metadata.get('Name')}
invalid={name:versions[name] for name,pin in pins.items() if versions[name] not in SpecifierSet('=='+pin)}
config=Path(sys.prefix,'pyvenv.cfg').read_text()
isolated=('include-system-site-packages = false' in config and sys.prefix!=sys.base_prefix and not site.ENABLE_USER_SITE)
external_sites=[p for p in sys.path if 'site-packages' in p and not Path(p).resolve().is_relative_to(Path(sys.prefix).resolve())]
print(json.dumps(dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,
isolated=isolated,external_site_packages=external_sites,required_versions=versions,all_installed_versions=all_versions,mismatched_pins=invalid)))
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--junit', type=Path, required=True)
    parser.add_argument('--write-lock', action='store_true', help='Write a platform-specific transitive version lock from this verified environment')
    args = parser.parse_args()
    requirements = ROOT / 'requirements.txt'
    pins = {}
    for line in requirements.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s]+)', line)
        if not match:
            raise ValueError('Expected an exact requirement pin: ' + line)
        pins[match[1]] = match[2]
    # Resolving the executable symlink would invoke the base interpreter and lose the venv.
    probe = subprocess.run([str(args.python.absolute()), '-I', '-c', PROBE], input=json.dumps(pins),
                           text=True, encoding='utf-8', capture_output=True, check=True)
    environment = json.loads(probe.stdout)
    if not environment['python'].startswith('3.13.'):
        raise ValueError('This validation workflow requires the recorded Python 3.13 target')
    if not environment['isolated'] or environment['external_site_packages'] or environment['mismatched_pins']:
        raise ValueError('Interpreter is not isolated or requirements are inconsistent')
    tests = ET.parse(args.junit).getroot().findall('.//testcase')
    if not tests or any(c.find('failure') is not None or c.find('error') is not None for c in tests):
        raise ValueError('Successful test evidence is required')
    skipped = sum(c.find('skipped') is not None for c in tests)
    if skipped == len(tests):
        raise ValueError('JUnit evidence contains no passing tests')
    report = dict(environment=environment, requirements_sha256=hashlib.sha256(requirements.read_bytes()).hexdigest(),
        tests=dict(passed=len(tests)-skipped, skipped=skipped, errors=0, failed=0,
                   junit_sha256=hashlib.sha256(args.junit.read_bytes()).hexdigest()),
        scope='Freshly created Python 3.13 environment; CPU torch wheel plus pinned requirements installed with uv. Existing source data and verified model weights are separate inputs.',
        upstream_source_rebuild=False, independent_clinical_validation=False)
    if args.write_lock:
        if environment['machine'] != 'x86_64' or not environment['platform'].startswith('Linux-'):
            raise ValueError('The named CPU lock targets Linux x86_64 only')
        lock = ROOT / 'requirements.cpu-py313.lock'
        lines = ['# Linux x86_64 / CPython 3.13 CPU environment; generated from the clean-install validation.',
                 '# Install the pinned CPU torch wheel from the official CPU index first; see docs/CONTINUED_SOURCE_WORK.md.',
                 '# Exact direct and transitive versions; wheel hashes and system libraries are not locked.']
        for name, version in sorted(environment['all_installed_versions'].items(), key=lambda item:item[0].casefold()):
            if not re.fullmatch('[A-Za-z0-9_.-]+', name) or re.search(r'\s', version):
                raise ValueError('Invalid installed package metadata')
            lines.append(name + '==' + version)
        lock.write_text('\n'.join(lines) + '\n', encoding="utf-8")
        report['transitive_version_lock'] = {'path':lock.name, 'packages':len(environment['all_installed_versions']),
            'sha256':hashlib.sha256(lock.read_bytes()).hexdigest(), 'scope':'recorded platform only; not a wheel-hash lock or upstream-data rebuild'}
    out = ROOT / 'reports/clean_install'
    out.mkdir(exist_ok=True)
    (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
