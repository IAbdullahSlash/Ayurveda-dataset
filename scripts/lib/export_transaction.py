"""Publish a validated snapshot and update legacy paths with rollback on errors.

Readers requiring a consistent multi-file view use current_export.json. Legacy paths
are not an atomic multi-file read API. A process crash before pointer replacement
leaves the previous snapshot authoritative.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid


def publish(root, staged, paths):
    root, staged = Path(root), Path(staged)
    snapshots = root / 'release' / 'snapshots'
    snapshots.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    hashes = {}
    for relative in sorted(paths):
        with (staged / relative).open('rb') as stream:
            hashes[relative] = hashlib.file_digest(stream, 'sha256').hexdigest()
        digest.update((relative + hashes[relative]).encode())
    snapshot = snapshots / digest.hexdigest()
    created = not snapshot.exists()
    if created:
        temporary = snapshots / ('.pending-' + uuid.uuid4().hex)
        try:
            shutil.copytree(staged, temporary)
            os.replace(temporary, snapshot)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    # Snapshot is immutable after this point. Existing content-addressed snapshots
    # are reused only if every file still matches its expected digest.
    for relative, expected in hashes.items():
        with (snapshot / relative).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('Corrupt export snapshot: ' + relative)
    touched = []
    with tempfile.TemporaryDirectory(prefix='.export-backup-', dir=root) as backup_dir:
        backup = Path(backup_dir)
        try:
            for relative in paths:
                target = root / relative
                prior = backup / relative
                if target.exists():
                    prior.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(target, prior)
                target.parent.mkdir(parents=True,exist_ok=True)
                temporary = target.with_name('.' + target.name + '.pending')
                try:
                    shutil.copy2(staged / relative, temporary)
                    os.replace(temporary, target)
                    touched.append(relative)
                finally:
                    temporary.unlink(missing_ok=True)
            pointer = root / 'release/current_export.json'
            temporary = pointer.with_suffix('.pending')
            temporary.write_text(json.dumps({'snapshot':str(snapshot.relative_to(root)), 'sha256':hashes},indent=2)+'\n')
            os.replace(temporary,pointer)
        except BaseException:
            for relative in reversed(touched):
                target, prior = root / relative, backup / relative
                if prior.exists():
                    os.replace(prior,target)
                else:
                    target.unlink(missing_ok=True)
            raise
    return snapshot


@contextmanager
def export_lock(path):
    """Serialize export builders on POSIX and Windows."""
    with open(path, 'a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
