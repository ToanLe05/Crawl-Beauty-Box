import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures'
sys.path.insert(0, str(ROOT))
import crawl_all_beautybox as c
from beautybox_data import parse_product


def markup(rows, total, slug='top-san-pham', product=None):
    queries = {'getAllProducts(' + json.dumps({'data': {'collections': slug}}) + ')': {'data': {'total': total, 'data': rows}}}
    if product:
        queries['getByIdProducts({})'] = {'data': product}
    state = {'productsApi': {'queries': queries}, 'cmsApi': {'queries': {}}}
    data = {'props': {'pageProps': {'initialReduxState': state}}}
    return '<html><body><script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script></body></html>'


class Tests(unittest.TestCase):
    def test_actual_initial_catalog(self):
        body = (FIXTURES / 'top1.html').read_text()
        total, rows = c.initial_listing(body, 'top-san-pham')
        self.assertGreater(total, 40)
        self.assertEqual(len(rows), 40)
        with self.assertRaises(ValueError):
            c.initial_listing(body, 'unrelated-collection')

    def test_actual_html_page_two_is_not_pagination(self):
        a = c.initial_listing((FIXTURES / 'top1.html').read_text(), 'top-san-pham')
        b = c.initial_listing((FIXTURES / 'top2.html').read_text(), 'top-san-pham')
        self.assertEqual([x['id'] for x in a[1]], [x['id'] for x in b[1]])
        with self.assertRaises(ValueError):
            c.merge_page(a[1], b[1], a[0], b[0])

    def test_actual_discovery_menu_and_brands(self):
        found = set()
        for name in ['home', 'brands', 'top1']:
            found |= c.discover((FIXTURES / f'{name}.html').read_text())[0]
        self.assertEqual(len(found), 101)
        self.assertIn(c.SITE + '/collections/banila-co', found)
        self.assertIn(c.SITE + '/collections/peripera', found)

    def test_canonical_reject_external_or_invalid(self):
        self.assertIsNone(c.canonical_url('https://other.example/collections/abc', 'collections'))
        self.assertIsNone(c.canonical_url('/collections/../admin', 'collections'))
        self.assertEqual(c.canonical_url('/collections/banila-co ', 'collections'), c.SITE + '/collections/banila-co')

    def test_actual_product_parser(self):
        body = (FIXTURES / 'validation_product.html').read_text()
        result = parse_product(body, 'https://beautybox.com.vn/products/fixture')
        self.assertTrue(result['product']['product_id'])
        self.assertTrue(result['product']['description_text'])
        self.assertIsInstance(result['variants'], list)
        self.assertNotIn('<style', result['product']['description_text'])

    def test_schema_and_duplicates(self):
        for bad in [{'data': [], 'total': True}, {'data': [], 'total': -1}, {'data': [{'slug': 'x'}], 'total': 1},
                    {'data': [{'id': 1, 'slug': 'x'}, {'id': 1, 'slug': 'x'}], 'total': 2}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                c.catalog_payload(bad)

    def test_total_change_or_empty_fails(self):
        for rows, total in [([], 2), ([{'id': 2}], 3)]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                c.merge_page([{'id': 1}], rows, 2, total)
        self.assertEqual(len(c.merge_page([{'id': 1}], [{'id': 2}], 2, 2)), 2)

    def test_http_denials_distinguished(self):
        for status in [401, 403, 429]:
            with self.assertRaises(c.AccessBlocked):
                c.raise_http(status, c.SITE)
        c.raise_http(200, c.SITE)

    def test_real_offset_pages_cover_97_unique_products(self):
        all_rows = []
        declared = None
        for offset in [0, 40, 80]:
            body = (FIXTURES / f'top_offset_{offset}.html').read_text()
            total, rows = c.initial_listing(body, 'top-san-pham', expected_offset=offset)
            if declared is None:
                declared, all_rows = total, rows
            else:
                all_rows = c.merge_page(all_rows, rows, declared, total)
        self.assertEqual(declared, 97)
        self.assertEqual(len(all_rows), 97)
        self.assertEqual(len({row['id'] for row in all_rows}), 97)

    def test_wrong_offset_rejected(self):
        body = (FIXTURES / 'top_offset_0.html').read_text()
        with self.assertRaises(ValueError):
            c.initial_listing(body, 'top-san-pham', expected_offset=40)

    def test_reader_uses_document_offset_without_xhr(self):
        calls = []
        class Reader(c.DocumentPagination):
            def navigate(self, url):
                calls.append(url)
                return (FIXTURES / 'top_offset_40.html').read_text()
        total, rows = Reader().next_page('top-san-pham', 2, offset=40)
        self.assertEqual(total, 97)
        self.assertEqual(len(rows), 40)
        self.assertTrue(calls[0].endswith('?limit=40&offset=40'))

    def test_zero_is_never_success(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); (p / 'details').mkdir()
            status = c.summarize(p, [], [], [], [])
            self.assertEqual(status['status'], 'incomplete')
            self.assertFalse(status['full_site_verified'])

    def test_end_to_end_check_control_and_exports(self):
        rows = [{'id': str(i), 'slug': f'product-{i}'} for i in range(1, 4)]
        class FakePage:
            def set_default_timeout(self, value): pass
            def is_closed(self): return False
            def content(self): return 'fixture'
        page = FakePage()
        browser = types.SimpleNamespace(new_context=lambda **kw: types.SimpleNamespace(new_page=lambda: page), close=lambda: None)
        pw = types.SimpleNamespace(chromium=types.SimpleNamespace(launch=lambda **kw: browser))
        @contextlib.contextmanager
        def fake_pw(): yield pw
        module = types.ModuleType('playwright.sync_api'); module.sync_playwright = fake_pw
        class FakeReader:
            def __init__(self, *args): pass
            def setup_robots(self): pass
            def navigate(self, url):
                if '/collections/' in url: return markup(rows[:2], 3)
                ident = url.rsplit('-', 1)[-1]
                return markup([], 0, product={'id': ident, 'detail': [{'langCode': 'vi', 'name': f'Product {ident}', 'htmlDescription': '<p>Công dụng: dưỡng ẩm</p>'}]})
            def next_page(self, slug, number, *, offset):
                assert offset == 2
                return 3, rows[2:]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'output'
            with patch.dict(sys.modules, {'playwright.sync_api': module}), patch.object(c, 'HttpReader', FakeReader), patch.object(sys, 'argv', ['crawl', '--check', '--output', str(out)]), contextlib.redirect_stdout(io.StringIO()):
                code = c.main()
            self.assertEqual(code, 0)
            status = c.load(out / 'status.json')
            self.assertEqual(status['status'], 'check_passed')
            self.assertEqual(status['known_catalog_products'], 3)
            self.assertEqual(status['exported_products'], 2)
            self.assertFalse(status['full_site_verified'])
            self.assertEqual(status['missing_product_ids'], [])
            self.assertEqual(status['intentionally_skipped_details'], 1)
            self.assertTrue((out / 'products.csv').read_bytes().startswith(b'\xef\xbb\xbf'))
            with patch.object(sys, 'argv', ['crawl', '--check', '--output', str(out), '--resume']), patch.dict(sys.modules, {'playwright.sync_api': module}), patch.object(c, 'HttpReader', FakeReader), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(c.main(), 0)
            self.assertEqual(len(list((out / 'details').glob('*.json'))), 2)

    def test_conflict_still_writes_incomplete_status(self):
        records = [{'url': 'one', 'items': [{'id': '1', 'slug': 'a'}], 'status': 'complete', 'pages_read': 1},
                   {'url': 'two', 'items': [{'id': '1', 'slug': 'b'}], 'status': 'complete', 'pages_read': 1}]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp); (out / 'details').mkdir()
            errors = []
            status = c.summarize(out, records, ['one', 'two'], ['one', 'two'], errors)
            self.assertEqual(status['status'], 'incomplete')
            self.assertTrue(any(x.get('type') == 'catalog_conflict' for x in status['errors']))
            self.assertEqual(status['known_catalog_products'], 1)
            self.assertTrue((out / 'status.json').exists())

    def test_resume_requires_output(self):
        with patch.object(sys, 'argv', ['crawl', '--resume']), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result: c.main()
            self.assertEqual(result.exception.code, 2)


if __name__ == '__main__': unittest.main(verbosity=2)
