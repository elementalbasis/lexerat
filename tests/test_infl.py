from dataclasses import asdict
import json
import importlib.util
import unittest

from lexerat import parse, render


class InflectionFieldTests(unittest.TestCase):
    def test_arbitrary_values(self):
        for value in ['1', '2', '3', 'o-stem', 'jekmi', 'custom, free (text)', '']:
            with self.subTest(value=value):
                entry, = parse(f'@key(word) @infl( {value} )')
                self.assertEqual(entry.infl, value)
                self.assertEqual(json.loads(json.dumps(asdict(entry)))['infl'], value)

    def test_no_reference_resolution(self):
        entries = parse('@key(a) @infl(b) @key(b) @infl(a) @key(c) @infl(unknown)')
        self.assertEqual([e.infl for e in entries], ['b', 'a', 'unknown'])

    def test_entry_scope(self):
        first, second = parse('@key(a) @typ(v) @def(one) @infl(1) @def(two) @key(b)', sort=False)
        self.assertEqual(first.infl, '1')
        self.assertIsNone(second.infl)
        self.assertEqual(first.definitions[1].state, {'typ': 'v'})
        expression, = parse('@expr(a phrase) @infl(custom)')
        self.assertEqual(expression.infl, 'custom')

    def test_duplicate_and_orphan_diagnostics(self):
        for source in ['@infl(1)', '@key(a) @infl(1) @infl(2)', '@key(a) @infl() @infl(2)']:
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, r'fixture:1:\d+:'):
                    parse(source, 'fixture')

    @unittest.skipUnless(importlib.util.find_spec('jinja2'), 'requires optional Jinja2 dependency')
    def test_available_to_templates(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / 'test.html.j2'
            template.write_text('{{ entries[0].infl | html_escape }}')
            self.assertEqual(render(parse('@key(a) @infl(o-stem)'), template), 'o-stem')


if __name__ == '__main__':
    unittest.main()
