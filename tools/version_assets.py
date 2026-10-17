"""Version the complete local frontend import graph for GitHub Pages caches."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
# Only quoted, same-directory frontend assets. Data URLs and remote URLs stay intact.
REFERENCE = re.compile(r'''(?P<quote>["'])(?P<path>(?:\./)?[\w-]+\.(?:mjs|js|css))(?:\?v=[0-9a-f]+)?(?P=quote)''')


def version_site(site):
    files = sorted(p for p in site.iterdir() if p.suffix in {'.js', '.mjs', '.css', '.html'})
    normalized = {p: REFERENCE.sub(lambda m: m['quote'] + m['path'] + m['quote'], p.read_text()) for p in files}
    digest = hashlib.sha256()
    for p, text in normalized.items():
        digest.update(p.name.encode() + b'\0' + text.encode() + b'\0')
    version = digest.hexdigest()[:20]
    for p, text in normalized.items():
        def replace(m):
            if not (site / m['path']).is_file():
                return m[0]
            return m['quote'] + m['path'] + '?v=' + version + m['quote']
        p.write_text(REFERENCE.sub(replace, text))
    return version


def version_artifact(root=ROOT):
    version = version_site(root / 'site')
    report_path = root / 'build-report.json'
    report = json.loads(report_path.read_text())
    report['frontendVersion'] = version
    report['siteBytes'] = sum(p.stat().st_size for p in (root / 'site').rglob('*') if p.is_file())
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return version


if __name__ == '__main__':
    print('Frontend version:', version_artifact())
