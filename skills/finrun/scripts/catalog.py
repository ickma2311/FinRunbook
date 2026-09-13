#!/usr/bin/env python3
"""Fetch versioned method text; never execute downloads or send research content."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

REPOSITORY = 'ickma2311/FinRunbook'
LIMIT = 512 * 1024
REVISION = re.compile(r'^[0-9a-f]{40}$')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def relative(value):
    p = PurePosixPath(value)
    if (not value or p.is_absolute() or '\\' in value or '%' in value or
            any(part in ('', '.', '..') for part in value.split('/'))):
        raise ValueError('unsafe relative path')
    return str(p)


def workspace_path(workspace, value):
    workspace = Path(workspace).resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    if candidate.is_symlink():
        raise ValueError('symlink output is not allowed')
    result = candidate.resolve()
    if not result.is_relative_to(workspace):
        raise ValueError('output must remain inside the caller workspace')
    # A packaged skill may never use its own installation as a workspace.
    install = Path(__file__).resolve().parents[3]
    if (install / '.codex-plugin/plugin.json').exists() and result.is_relative_to(install):
        raise ValueError('choose a workspace outside the installed plugin')
    return result


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    if tmp.is_symlink():
        raise ValueError('symlink temporary file is not allowed')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def raw_url(repo, revision, path):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not REVISION.fullmatch(revision):
        raise ValueError('repository and immutable 40-character commit required')
    return f'https://raw.githubusercontent.com/{repo}/{revision}/{relative(path)}'


def canonical(url):
    u = urlsplit(url)
    if u.scheme != 'https' or u.query or u.fragment or u.username or u.port:
        raise ValueError('method URLs must be plain HTTPS immutable GitHub URLs')
    parts = u.path.lstrip('/').split('/')
    if u.netloc == 'github.com' and len(parts) >= 5 and parts[2] == 'blob':
        repo, rev, path = '/'.join(parts[:2]), parts[3], '/'.join(parts[4:])
    elif u.netloc == 'raw.githubusercontent.com' and len(parts) >= 4:
        repo, rev, path = '/'.join(parts[:2]), parts[2], '/'.join(parts[3:])
    else:
        raise ValueError('only pinned GitHub instruction text is supported')
    if not path.endswith('.md'):
        raise ValueError('only Markdown instruction text may be fetched')
    return raw_url(repo, rev, path), repo, rev, path


def download(url):
    request = Request(url, headers={'User-Agent': 'Finrun/0.5 public-method-reader', 'Accept': 'application/json,text/plain'})
    with urlopen(request, timeout=20) as response:
        if response.url != url:
            raise ValueError('unexpected redirect while retrieving method text')
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise ValueError('catalog/method exceeds 512 KiB limit')
    return data


def parse_catalog(text, repo, rev):
    if '<!-- finrun-catalog: 1 -->' not in text:
        raise ValueError('catalog is not compatible with Finrun 0.5; publish the new catalog or use an explicit compatible commit')
    methods = []
    for line in text.splitlines():
        if not line.startswith('| '):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 3:
            raise ValueError('catalog needs three columns')
        name, description, link = cells
        if name in ('Method', 'Skill', '---') or set(name) <= set('-: '):
            continue
        match = re.fullmatch(r'\[Read\]\(([^)]+)\)', link)
        if not match or not name or len(description.split()) < 4:
            raise ValueError('catalog entry lacks a useful description or instruction link')
        target = match.group(1)
        url = canonical(target)[0] if target.startswith('https://') else raw_url(repo, rev, 'skills/' + relative(target))
        canonical(url)
        if any(m['name'] == name for m in methods):
            raise ValueError('duplicate catalog method name')
        methods.append({'name': name, 'description': description, 'url': url})
    if not methods:
        raise ValueError('empty catalog')
    return methods


class Catalog:
    def __init__(self, workspace, transport=download, repo=REPOSITORY):
        self.workspace = Path(workspace).resolve()
        raw_url(repo, '0' * 40, 'skills/index.md')
        self.repo, self.transport = repo, transport
        self.cache = workspace_path(self.workspace, 'run/.cache/skills')

    def cached_file(self, url):
        url, repo, rev, path = canonical(url)
        return workspace_path(self.workspace, self.cache / repo / rev / (path + '.json'))

    def read_cache(self, url):
        entry = json.loads(self.cached_file(url).read_text())
        if not isinstance(entry, dict) or not isinstance(entry.get('text'), str):
            raise ValueError('invalid cached instruction object')
        text = entry['text']; data = text.encode('utf-8')
        if entry['url'] != url or entry['sha256'] != digest(data) or len(data) > LIMIT or '\x00' in text:
            raise ValueError('cache metadata or content hash mismatch')
        return entry

    def get(self, url, offline=False):
        url = canonical(url)[0]
        try:
            entry = self.read_cache(url)
            return {**entry, 'cache_used': True}
        except (OSError, ValueError, KeyError, TypeError):
            if offline:
                raise ValueError('matching cached instruction missing or corrupt: ' + url)
        data = self.transport(url)
        text = data.decode('utf-8')
        if len(data) > LIMIT or '\x00' in text:
            raise ValueError('invalid instruction text')
        entry = dict(url=url, sha256=digest(data), retrieved_at=now(), text=text)
        write_json(self.cached_file(url), entry)
        return {**entry, 'cache_used': False}

    def resolve(self, revision=None, offline=False):
        requested_revision = revision
        if revision is not None and not REVISION.fullmatch(revision):
            raise ValueError('explicit revision must be an immutable 40-character commit')
        pointer = workspace_path(self.workspace, self.cache / self.repo / 'last-good.json')
        reason = None
        try:
            if offline:
                raise OSError('offline requested')
            if revision is None:
                commits = json.loads(self.transport(f'https://api.github.com/repos/{self.repo}/commits?per_page=1'))
                revision = commits[0]['sha']
            url = raw_url(self.repo, revision, 'skills/index.md')
            entry = self.get(url)
            methods = parse_catalog(entry['text'], self.repo, revision)
            write_json(pointer, {'revision': revision, 'sha256': entry['sha256']})
        except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
            reason = str(error)
            # An explicit commit may use only its own cache, never a different last-good revision.
            if requested_revision is not None:
                try:
                    url = raw_url(self.repo, revision, 'skills/index.md')
                    entry = self.read_cache(url)
                    methods = parse_catalog(entry['text'], self.repo, revision)
                except (OSError, ValueError, KeyError, TypeError):
                    raise ValueError('requested catalog unavailable; no valid matching cache: ' + reason) from error
            else:
                try:
                    saved = json.loads(pointer.read_text()); revision = saved['revision']
                    url = raw_url(self.repo, revision, 'skills/index.md'); entry = self.read_cache(url)
                    if saved['sha256'] != entry['sha256']:
                        raise ValueError('last-good catalog hash mismatch')
                    methods = parse_catalog(entry['text'], self.repo, revision)
                except (OSError, ValueError, KeyError, TypeError) as cache_error:
                    raise ValueError('catalog unavailable and no valid cache; enable network or publish a compatible catalog: ' + reason) from cache_error
        return dict(schema_version=1, repository=self.repo, catalog_commit=revision, catalog_url=url,
                    catalog_sha256=entry['sha256'], resolved_at=now(), fallback_reason=reason,
                    methods=methods, selected=[])

    def fetch(self, receipt, names=(), supports=(), offline=False):
        rev = receipt['catalog_commit']
        url = raw_url(self.repo, rev, 'skills/index.md')
        entry = self.get(url, offline)
        if receipt['repository'] != self.repo or receipt['catalog_sha256'] != entry['sha256']:
            raise ValueError('request catalog receipt does not match pinned content')
        methods = parse_catalog(entry['text'], self.repo, rev)
        selected = list(receipt.get('selected', []))
        targets = []
        for name in names:
            match = next((x for x in methods if x['name'] == name), None)
            if not match:
                raise ValueError('unknown method: ' + name)
            if 'unavailable' in match['description'].lower():
                raise ValueError('method is marked unavailable for this plugin: ' + name)
            targets.append((name, match['url']))
        for support in supports:
            target, repo, commit, _ = canonical(support)
            parents = [canonical(x['url']) for x in selected] + [canonical(u) for _, u in targets]
            if not any(parent[1:3] == (repo, commit) for parent in parents):
                raise ValueError('supporting text must share a selected method repository and commit')
            targets.append(('supporting-reference', target))
        for name, target in targets:
            content = self.get(target, offline)
            item = {k: content[k] for k in ('url', 'sha256', 'retrieved_at', 'cache_used')}
            item.update(name=name, cache_path=str(self.cached_file(target).relative_to(self.workspace)))
            prior = next((x for x in selected if x['url'] == target), None)
            if prior and prior['sha256'] != item['sha256']:
                raise ValueError('selected method changed despite an immutable URL')
            if not prior:
                selected.append(item)
        return {**receipt, 'selected': selected}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['resolve', 'fetch'])
    p.add_argument('--workspace', type=Path, default=Path.cwd())
    p.add_argument('--receipt', required=True, help='Workspace-relative JSON receipt; existing receipt stays pinned')
    p.add_argument('--revision', help='Explicit published test commit; otherwise resolve default branch')
    p.add_argument('--method', action='append', default=[])
    p.add_argument('--support', action='append', default=[])
    p.add_argument('--offline', action='store_true')
    args = p.parse_args()
    try:
        c = Catalog(args.workspace); path = workspace_path(args.workspace, args.receipt)
        if args.command == 'resolve':
            if path.exists():
                raise ValueError('receipt already exists; use fetch to continue its pinned version')
            result = c.resolve(args.revision, args.offline)
        else:
            result = c.fetch(json.loads(path.read_text()), args.method, args.support, args.offline)
        write_json(path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as error:
        p.exit(2, f'Finrun catalog: {error}\n')


if __name__ == '__main__':
    main()
