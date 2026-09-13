"""Additional checks for the small Finrun contract; legacy records stay readable."""
import ast
import hashlib
import json
import math
import re
from pathlib import Path


def arithmetic(expression, variables):
    tree = ast.parse(expression, mode='eval')
    if len(list(ast.walk(tree))) > 100:
        raise ValueError('expression is too complex')
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name) and node.id in variables:
            return variables[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): return a + b
            if isinstance(node.op, ast.Sub): return a - b
            if isinstance(node.op, ast.Mult): return a * b
            if isinstance(node.op, ast.Div): return a / b
            if isinstance(node.op, ast.Pow) and abs(b) <= 12: return a ** b
        raise ValueError('only numeric inputs and + - * / ** arithmetic are allowed')
    value = visit(tree)
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('non-finite arithmetic result')
    return value


def check(record, run_dir, verified_market_calculations=()):
    if record.get('workflow') != 'finrun-0.5':
        return []
    issues = []
    def error(code, message, path):
        issues.append(dict(severity='error', code=code, message=message, path=path))
    review = record.get('review', {})
    if (not isinstance(review, dict) or review.get('status') != 'completed'
            or not isinstance(review.get('notes'), list) or not review['notes']
            or not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()
            or not all(isinstance(n, str) and n.strip() for n in review['notes'])):
        error('review.incomplete', 'Review material claims, periods, arithmetic and language; then record completed status and notes.', 'review')
    try:
        path = (run_dir / 'methods.json').resolve()
        if not path.is_relative_to(run_dir.resolve()):
            raise ValueError('method receipt must remain inside the run')
        receipt = json.loads(path.read_text())
        if receipt['schema_version'] != 1 or not re.fullmatch('[0-9a-f]{40}', receipt['catalog_commit']):
            raise ValueError('invalid catalog receipt revision/schema')
        if not re.fullmatch('[0-9a-f]{64}', receipt['catalog_sha256']) or not receipt['selected']:
            raise ValueError('method receipt needs a catalog hash and selected methods')
        for item in receipt['selected']:
            if not re.fullmatch('[0-9a-f]{64}', item['sha256']) or not item.get('retrieved_at'):
                raise ValueError('selected method needs its hash and retrieval timestamp')
            if not re.fullmatch(r'https://raw\.githubusercontent\.com/[\w.-]+/[\w.-]+/[0-9a-f]{40}/[^?#]+\.md', item['url']):
                raise ValueError('selected method must reference immutable GitHub Markdown')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        error('methods.receipt', str(exc), 'methods.json')
    facts = {f['id']: f for f in record.get('facts', []) if isinstance(f, dict) and 'id' in f}
    for c in record.get('calculations', []):
        if isinstance(c, dict) and c.get('id') in verified_market_calculations:
            continue  # Already recomputed from hashed bars by the market-data validator.
        try:
            inputs = c['inputs']
            if not isinstance(inputs, dict) or set(inputs.values()) != set(c['input_fact_ids']):
                raise ValueError('inputs must map expression variable names to exactly input_fact_ids')
            values = {name: facts[fid]['value'] for name, fid in inputs.items()}
            if not all(type(v) in (int, float) and math.isfinite(v) for v in values.values()):
                raise ValueError('calculation inputs must be finite numeric facts')
            actual = arithmetic(c['expression'], values)
            if type(c['result']) not in (int, float) or not math.isclose(actual, c['result'], rel_tol=1e-9, abs_tol=1e-8):
                raise ValueError('stored result differs from recomputed arithmetic')
        except (ValueError, TypeError, KeyError, SyntaxError, ArithmeticError) as exc:
            error('calculation.recompute', str(exc), str(c.get('id', 'calculations')) if isinstance(c, dict) else 'calculations')
    for s in record.get('sources', []):
        if not isinstance(s, dict) or not s.get('local_path'):
            continue
        try:
            rel = Path(s['local_path']); path = (run_dir / rel).resolve()
            if rel.is_absolute() or not path.is_relative_to(run_dir.resolve()) or not path.is_file():
                raise ValueError('source snapshot must be a real run-relative file')
            if hashlib.sha256(path.read_bytes()).hexdigest() != s.get('sha256'):
                raise ValueError('source snapshot SHA-256 is missing or mismatched')
        except (OSError, ValueError, TypeError) as exc:
            error('source.snapshot', str(exc), s.get('id', 'sources'))
    return issues
