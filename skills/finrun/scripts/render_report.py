#!/usr/bin/env python3
"""Render a portable evidence-linked report and requested CSV from structured data."""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from urllib.parse import urlsplit


def safe(root, rel):
    if Path(rel).is_absolute() or not (root / rel).resolve().is_relative_to(root.resolve()):
        raise ValueError('artifact must be run-relative')
    return root / rel


def csv_value(value):
    if isinstance(value, dict): value = value.get('value')
    if value is None: return ''
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value
    return value


def render(root):
    root = root.resolve()
    install = Path(__file__).resolve().parents[3]
    if (install / '.codex-plugin/plugin.json').exists() and root.is_relative_to(install):
        raise ValueError('choose a workspace outside the installed plugin')
    record_path = safe(root, 'research-record.json')
    r = json.loads(record_path.read_text())
    data_path = safe(root, 'report/report-data.json')
    d = json.loads(data_path.read_text())
    for key in ('sources', 'facts', 'evidence', 'calculations'):
        d[key] = r[key]
    facts = {x['id']: x for x in r['facts']}; calcs = {x['id']: x for x in r['calculations']}
    known = {'fact_ids': set(facts), 'calculation_ids': set(calcs), 'source_ids': {s['id'] for s in r['sources']}}
    if not d.get('sections') or not d['executive_view'].get('headline') or not d['executive_view'].get('summary'):
        raise ValueError('populate the analytical sections and executive view before rendering')
    for s in r['sources']:
        if s.get('url'):
            u = urlsplit(s['url'])
            if u.scheme not in ('https', 'http') or not u.netloc or u.username:
                raise ValueError('unsafe source URL')
        elif s.get('local_path'):
            safe(root, s['local_path'])
    displayed_facts = set()
    def visit(x):
        if isinstance(x, dict):
            for key, ids in known.items():
                if key in x and (not isinstance(x[key], list) or not set(x[key]) <= ids):
                    raise ValueError('unknown presentation reference: ' + key)
                if key == 'fact_ids':
                    displayed_facts.update(x.get(key, []))
            for v in x.values(): visit(v)
        elif isinstance(x, list):
            for v in x: visit(v)
    for block in [d['executive_view']] + d['sections'] + d.get('methodology', []): visit(block)
    for section in d['sections']:
        if section.get('type') not in ('analysis', 'table', 'chart', 'ranking'):
            raise ValueError('unsupported standard section type')
        for row in section.get('rows', []):
            for cell in row.values():
                if type(cell) in (int, float):
                    raise ValueError('numeric cells require value, evidence, period, units and basis')
                if not isinstance(cell, dict) or cell.get('value') is None: continue
                if type(cell['value']) not in (int, float) or not math.isfinite(cell['value']):
                    raise ValueError('metric value must be a finite number or null')
                if not cell.get('period') or not cell.get('units') or cell.get('basis') not in ('actual', 'guidance', 'estimate', 'scenario'):
                    raise ValueError('metric lacks period, units or actual/guidance/estimate/scenario basis')
                ids = cell.get('calculation_ids', []) or cell.get('fact_ids', [])
                if len(ids) != 1:
                    raise ValueError('metric cell needs one primary fact or calculation')
                item = calcs[ids[0]] if ids[0] in calcs else facts[ids[0]]
                value = item.get('result', item.get('value'))
                scale = cell.get('scale', 1)
                if type(scale) not in (int, float) or not math.isfinite(scale) or not math.isclose(value * scale, cell['value'], rel_tol=1e-9, abs_tol=1e-8):
                    raise ValueError('display value does not match its cited fact/calculation and scale')
    d['validation'] = r['validation']
    d['meta']['language'] = r['request']['language']
    for artifact in r['artifacts']:
        if artifact['path'].startswith('report/'):
            artifact['fact_ids'] = sorted(displayed_facts)
    data_path.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    record_path.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    if any(a['format'] == 'interactive-html' for a in r['artifacts']):
        template = (Path(__file__).resolve().parents[1] / 'assets/report.html').read_text()
        payload = json.dumps(d, ensure_ascii=False).replace('<', '\\u003c')
        safe(root, 'report/index.html').write_text(template.replace('__FINRUN_DATA__', payload))
    if any(a['format'] == 'csv' for a in r['artifacts']):
        table = next((s for s in d['sections'] if s.get('columns') and s.get('rows')), None)
        if not table: raise ValueError('CSV requires a populated table')
        with safe(root, 'report/datasheet.csv').open('w', newline='') as out:
            writer = csv.writer(out)
            writer.writerow([csv_value(c['label']) for c in table['columns']])
            for row in table['rows']:
                writer.writerow([csv_value(row.get(c['key'])) for c in table['columns']])
    return root / 'report'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('run_directory', type=Path)
    try: print(render(p.parse_args().run_directory))
    except (OSError, ValueError, KeyError, TypeError) as e: p.exit(2, f'Finrun renderer: {e}\n')
