#!/usr/bin/env python3
"""Offline checks for the public documentation, tools, and release scripts."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
import ast
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    errors = []
    version = (ROOT / 'VERSION').read_text().strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        errors.append('VERSION must contain a semantic release number')
    files = list((ROOT / 'examples').glob('*.md')) + list(ROOT.glob('*.md')) + list((ROOT / 'docs').rglob('*.md')) + list((ROOT / 'Tools').glob('*.md'))
    for path in files:
        text = path.read_text(encoding='utf-8')
        if 'v1.0.13' in text:
            errors.append(f'{path.relative_to(ROOT)}: stale v1.0.13 release reference')
        fence = None
        for line in text.splitlines():
            match = re.match(r'^\s*(`{3,}|~{3,})', line)
            if match:
                delimiter = match[1]
                if fence is None:
                    fence = delimiter
                elif delimiter[0] == fence[0] and len(delimiter) >= len(fence):
                    fence = None
        if fence:
            errors.append(f'{path.relative_to(ROOT)}: unclosed code fence')
        links = re.findall(r'\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text)
        links += re.findall(r'(?:src|href)="([^"]+)"', text)
        for link in links:
            target = urlsplit(link.strip('<>'))
            if target.scheme or target.netloc or not target.path:
                continue
            destination = (ROOT if target.path.startswith('/') else path.parent) / unquote(target.path.lstrip('/'))
            if not destination.exists():
                errors.append(f'{path.relative_to(ROOT)}: missing link {link}')
    for folder in ('Tools', 'scripts'):
        for path in (ROOT / folder).rglob('*.py'):
            try:
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            except SyntaxError as error:
                errors.append(str(error))
    for path in (ROOT / 'scripts').rglob('*.sh'):
        result = subprocess.run(['bash', '-n', str(path)], capture_output=True, text=True)
        if result.returncode:
            errors.append(result.stderr.strip())
    for path in (ROOT / 'docs/releases').glob('*.json'):
        try:
            manifest = json.loads(path.read_text())
            if path.name.endswith('-build.json'):
                if manifest['version'] != path.name.removeprefix('v').removesuffix('-build.json') or not manifest['build_id']:
                    raise ValueError('invalid runtime build identity')
                for key in ('runtime_sha256', 'config_sha256'):
                    if not re.fullmatch(r'[a-f0-9]{64}', manifest[key]):
                        raise ValueError('invalid runtime/config SHA-256')
                continue
            parts = manifest['parts']
            if not parts or sum(p['size_bytes'] for p in parts) != manifest['archive_size_bytes']:
                raise ValueError('part sizes do not add up to the archive size')
            if len({p['name'] for p in parts}) != len(parts):
                raise ValueError('duplicate archive part names')
            for part in parts:
                if not 0 < part['size_bytes'] <= manifest['part_size_limit_bytes'] < 2_000_000_000:
                    raise ValueError('part exceeds the release size limit')
                if not re.fullmatch(r'[a-f0-9]{64}', part['sha256']):
                    raise ValueError('invalid SHA-256')
        except (ValueError, KeyError, TypeError) as error:
            errors.append(f'{path.relative_to(ROOT)}: {error}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'PASS: v{version}; {len(files)} Markdown files; local links, fences, Python, Bash and release metadata')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
