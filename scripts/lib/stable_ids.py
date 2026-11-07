"""Append-only concept IDs with explicit, reviewed aliases for renamed concepts."""
import csv
import json
import os
from pathlib import Path
import tempfile
from lib.export_transaction import export_lock

REGISTRY = Path(__file__).resolve().parents[2] / 'curation/id_registry.json'
ALIASES = REGISTRY.with_name('id_aliases.csv')
PREFIXES = {'herbs': ('HERB-', 4), 'symptoms': ('SYM-N', 5)}

def approved_aliases(namespace, path):
    if not path.exists():
        return {}
    aliases = {}
    with path.open(newline='',encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            if row['namespace'] != namespace or row['decision'] != 'approved':
                continue
            if not all(row.get(k,'').strip() for k in ['alias','canonical_key','reference','reviewer']):
                raise ValueError('Approved ID alias lacks review evidence')
            alias, canonical = row['alias'], row['canonical_key']
            if alias in aliases and aliases[alias] != canonical:
                raise ValueError('Conflicting ID alias: ' + alias)
            aliases[alias] = canonical
    return aliases

def allocate(namespace, keys):
    prefix, width = PREFIXES[namespace]
    with export_lock(REGISTRY.with_suffix('.lock')):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        mapping = registry.setdefault(namespace, {})
        if len(set(mapping.values())) != len(mapping):
            raise ValueError('Duplicate IDs in registry: ' + namespace)
        aliases = approved_aliases(namespace, ALIASES)
        def canonical(key):
            seen = set()
            while key in aliases:
                if key in seen:
                    raise ValueError('Cyclic ID alias')
                seen.add(key)
                key = aliases[key]
            return key
        for alias in aliases:
            target = canonical(alias)
            if target not in mapping:
                raise ValueError('Alias target must be an existing identity: ' + target)
            if alias in mapping and mapping[alias] != mapping[target]:
                raise ValueError('Alias would merge distinct published IDs: ' + alias)
        next_id = max((int(v[len(prefix):]) for v in mapping.values()), default=0) + 1
        changed = False
        for key in sorted(set(map(canonical, keys))):
            if key not in mapping:
                mapping[key] = f'{prefix}{next_id:0{width}d}'
                next_id += 1
                changed = True
        if changed:
            fd, temporary = tempfile.mkstemp(prefix='.ids-',dir=REGISTRY.parent)
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as stream:
                    json.dump(registry,stream,ensure_ascii=False,indent=2)
                    stream.write('\n')
                os.replace(temporary,REGISTRY)
            finally:
                Path(temporary).unlink(missing_ok=True)
        return {**mapping, **{alias:mapping[canonical(alias)] for alias in aliases}}
