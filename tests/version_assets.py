import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from version_assets import version_artifact


class AssetVersions(unittest.TestCase):
    def test_nested_imports_cache_and_repeatability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site = root / 'site'
            site.mkdir()
            (root / 'build-report.json').write_text('{}')
            (site / 'index.html').write_text('<script src="app.js"></script><link href="style.css">')
            (site / 'app.js').write_text("import {x} from './nested.mjs'; fetch('release.json');")
            (site / 'nested.mjs').write_text('export const x=1;')
            (site / 'style.css').write_text('body {color: black;}')
            (site / 'release.json').write_text('{"data":"unchanged"}')
            first = version_artifact(root)
            self.assertIn('app.js?v=' + first, (site / 'index.html').read_text())
            self.assertIn('style.css?v=' + first, (site / 'index.html').read_text())
            self.assertIn('./nested.mjs?v=' + first, (site / 'app.js').read_text())
            before = {p.name: p.read_bytes() for p in site.iterdir()}
            self.assertEqual(first, version_artifact(root))
            self.assertEqual(before, {p.name: p.read_bytes() for p in site.iterdir()})
            (site / 'nested.mjs').write_text('export const x=2;')
            second = version_artifact(root)
            self.assertNotEqual(first, second)
            self.assertIn('app.js?v=' + second, (site / 'index.html').read_text())
            self.assertIn('./nested.mjs?v=' + second, (site / 'app.js').read_text())
            self.assertEqual((site / 'release.json').read_text(), '{"data":"unchanged"}')
            self.assertEqual(json.loads((root / 'build-report.json').read_text())['siteBytes'], sum(p.stat().st_size for p in site.iterdir()))


if __name__ == '__main__':
    unittest.main()
