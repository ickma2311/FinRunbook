#!/usr/bin/env python3
"""Build an allowlisted, deterministic Codex archive without external sources."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(data): return hashlib.sha256(data).hexdigest()


def checked_path(root, rel):
    p = PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts or '\\' in rel:
        raise ValueError('unsafe package path')
    path = root / rel
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('package source/output escapes its root')
    return path


def build(root=ROOT):
    root = root.resolve()
    declared = json.loads((root / 'plugin/runtime-files.json').read_text())
    manifest = json.loads((root / 'plugin/manifest.json').read_text())
    if manifest['name'] != 'finrun' or any(k in manifest for k in ('apps', 'mcpServers', 'hooks')):
        raise ValueError('expected one local Finrun plugin with no remote runtime')
    if [p for p in declared if p.endswith('/SKILL.md')] != ['skills/finrun/SKILL.md']:
        raise ValueError('bundle must have exactly one skill entry')
    content = {}
    for target, source in declared.items():
        checked_path(root, target)
        if target.startswith(('run/', 'tests/', 'examples/', 'skills/methods/')) or target.endswith(('.pyc', '.app.json', '.mcp.json')):
            raise ValueError('undeployable package content')
        file = checked_path(root, source)
        if not file.is_file(): raise ValueError('missing declared runtime file: ' + source)
        content[target] = file.read_bytes()
    snapshot = sha(json.dumps({k: sha(v) for k,v in sorted(content.items())}, sort_keys=True).encode())
    base = checked_path(root, 'run/.build')
    base.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix=f'{manifest["version"]}-', dir=base))
    plugin = out / 'finrun'
    for rel, data in content.items():
        p = checked_path(plugin, rel); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    archive = out / f'finrun-{manifest["version"]}.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, data in sorted(content.items()):
            info = zipfile.ZipInfo('finrun/' + rel, date_time=(1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    git = subprocess.run(['git','rev-parse','HEAD'], cwd=root, capture_output=True, text=True)
    receipt = dict(version=manifest['version'], plugin=str(plugin), archive=str(archive),
                   sha256=sha(archive.read_bytes()), source_snapshot_sha256=snapshot,
                   repository_revision=git.stdout.strip() if git.returncode==0 else None,
                   files={k: {'source': declared[k], 'sha256': sha(v), 'bytes': len(v)} for k,v in sorted(content.items())},
                   note='Snapshot hashes describe the exact built bytes, including uncommitted implementation. Build does not install or publish.')
    (out / 'BUILD.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try: print(json.dumps(build(), indent=2))
    except (OSError, ValueError, KeyError) as e: parser.exit(2, f'Finrun build: {e}\n')
