from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]


def fingerprint(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob('*') if path.is_file()
    }


class RepositoryLayoutTest(unittest.TestCase):
    def test_only_product_folders_and_no_internal_runtime(self):
        product = {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith('.')}
        self.assertEqual(product, {'skills', 'plugin', 'run', 'tests', 'examples'})
        self.assertFalse((ROOT / '.gitmodules').exists())
        for name in ('finrunbook-investor', 'finrunbook-hourly'):
            self.assertFalse((ROOT / 'skills' / name).exists())

    def test_local_instruction_links_resolve(self):
        pages = [ROOT / 'README.md', ROOT / 'AGENTS.md', *list((ROOT / 'skills').rglob('*.md'))]
        for page in pages:
            for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', page.read_text()):
                if urlsplit(link).scheme or link.startswith('#'):
                    continue
                target = (page.parent / link.split('#', 1)[0]).resolve()
                self.assertTrue(target.is_relative_to(ROOT), (page, link))
                self.assertTrue(target.exists(), (page, link))

    def test_catalog_has_descriptions_and_immutable_upstream_paths(self):
        text = (ROOT / 'skills/index.md').read_text()
        rows = [row for row in text.splitlines() if row.startswith('| ')][2:]
        self.assertTrue(rows)
        names = set()
        for row in rows:
            name, description, instruction = [cell.strip() for cell in row.strip('|').split('|')]
            self.assertNotIn(name, names)
            names.add(name)
            self.assertGreater(len(description.split()), 3)
            match = re.fullmatch(r'\[Read\]\(([^)]+)\)', instruction)
            self.assertIsNotNone(match)
            link = match.group(1)
            if link.startswith('https://'):
                self.assertRegex(link, r'^https://github\.com/[^/]+/[^/]+/blob/[0-9a-f]{40}/.+/SKILL\.md$|^https://github\.com/[^/]+/[^/]+/blob/[0-9a-f]{40}/SKILL\.md$')
            else:
                self.assertTrue((ROOT / 'skills' / link).is_file())

    def test_relocated_helpers_write_only_in_callers_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory).resolve()
            installed = scratch / 'separate-source'
            runtime = installed / 'skills/finrun'
            shutil.copytree(ROOT / 'skills/finrun', runtime, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            workspace = scratch / 'workspace'
            workspace.mkdir()
            before = fingerprint(installed)
            commands = [
                ['new_run.py', '--subject', 'Example', '--request', 'Analyze Example', '--run-id', 'company-example'],
                ['new_batch.py', '--request', 'Find financial topics', '--language', 'zh-CN', '--batch-id', 'radar-example'],
            ]
            for script, *args in commands:
                result = subprocess.run([sys.executable, '-B', str(runtime / 'scripts' / script), *args],
                                        cwd=workspace, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(Path(result.stdout.strip()).is_relative_to(workspace / 'run'))
            run = workspace / 'run/company-example'
            self.assertTrue((run / 'research-record.json').is_file())
            radar = json.loads((workspace / 'run/radar-example/radar.json').read_text())
            self.assertEqual(radar['request']['language'], 'zh-CN')
            # An unfinished record must still fail financial validation after relocation.
            result = subprocess.run([sys.executable, '-B', str(runtime / 'scripts/validate_run.py'), str(run)],
                                    cwd=workspace, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads((run / 'validation.json').read_text())['status'], 'FAIL')
            self.assertEqual(fingerprint(installed), before)
            self.assertEqual({p.name for p in workspace.iterdir()}, {'run'})

    def test_generated_content_is_ignored_in_clean_git_checkout(self):
        # Isolated repo makes this work in both Git worktrees and plain source exports.
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory)
            shutil.copy2(ROOT / '.gitignore', checkout / '.gitignore')
            subprocess.run(['git', 'init', '-q', str(checkout)], check=True, capture_output=True)
            paths = ['run/private/report.json', 'run/.cache/skills/catalog.md',
                     'run/.cache/data/source.json', 'run/.venv/bin/python',
                     'run/.build/finrun.zip', 'portfolio/account.json',
                     'skills/finrunbook-hourly/SKILL.md']
            result = subprocess.run(['git', 'check-ignore', '--stdin'], cwd=checkout,
                                    input='\n'.join(paths) + '\n', capture_output=True, text=True)
            self.assertEqual(set(result.stdout.splitlines()), set(paths))
            result = subprocess.run(['git', 'check-ignore', 'run/README.md', 'skills/index.md', 'plugin/README.md'],
                                    cwd=checkout, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stdout)


if __name__ == '__main__':
    unittest.main()
