# Consistent export publication

Stage 08 validates input keys before writing, builds all outputs in a staging directory, validates SQLite, and publishes an immutable snapshot. `release/current_export.json` is atomically replaced only after publication succeeds. A reader requiring consistency across files must read this pointer once and resolve all paths inside its `snapshot` directory. SHA-256 values identify the validated file contents.

Traditional paths such as `release/ayurkb.sqlite` remain available for compatibility. They are updated with rollback if an operation raises an error; they are not a multi-file atomic read API. A killed process can interrupt these compatibility copies, but the previous snapshot pointer remains authoritative. Rerunning stage 08 restores consistent compatibility files. Builders are serialized with a filesystem lock.

Stage 13 verifies compatibility files against the manifest before packaging, includes requirements, citation and provenance, tests ZIP integrity, and atomically replaces the archive. It fails if processed inputs changed after stage 08. Offline model weights remain optional, so lexical use works without an embedding index. Snapshots are local generated artifacts; retain the currently referenced snapshot when cleaning up old versions.
