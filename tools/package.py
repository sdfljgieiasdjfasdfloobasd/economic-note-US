"""Create an allowlisted upload archive; private backups never leave this Mac."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import verify

ROOT=Path(__file__).resolve().parents[1]
if __name__ == '__main__':
    verify.verify()
    target=ROOT/'economic-dashboard-github.zip'
    paths=[ROOT/'README.md',ROOT/'.gitignore',ROOT/'build-report.json',ROOT/'publication-report.json']
    for folder in ['site','tools','templates','tests','.github','cloud']:
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for p in sorted(paths):
            if p.is_symlink(): raise ValueError('リンクは梱包しません。')
            z.write(p,'economic-dashboard-github/'+p.relative_to(ROOT).as_posix(),compress_type=ZIP_STORED if p.suffix=='.gz' else ZIP_DEFLATED)
    print(f'{target.name}: {target.stat().st_size/1_000_000:.2f} MB')
