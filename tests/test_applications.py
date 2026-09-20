import tempfile
import unittest
from pathlib import Path
from applications import Applications, prepare, revision
from shortlist import Store
from test_shortlist import fixture

class ApplicationTests(unittest.TestCase):
    def test_preparation_preserves_source_and_flags_missing(self):
        source = 'TEST PERSON\nEngineer, Example 2020–2023\nUsed Python for reports.\nNo Java experience.'
        record = prepare(source, 'Python, Kubernetes, Java')
        self.assertTrue(record['draft'].endswith(source))
        self.assertIn('kubernetes', record['missing'])
        self.assertNotIn('Kubernetes', record['draft'])
        self.assertIn('No Java experience.', record['draft'])
        self.assertFalse(record['reviewed'])
        with self.assertRaises(ValueError): prepare('', 'Python')
        with self.assertRaises(ValueError): prepare(source, '')

    def test_review_tracking_persistence_and_stale_forms(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'test.db'
            store = Store(path)
            first, _ = store.add(fixture())
            second, _ = store.add(fixture(link='https://example.com/jobs/2'))
            apps = Applications(store)
            record = apps.save(first, dict(action='generate', source='TEST PERSON\nUsed Python', requirements='Python, Rust'))
            self.assertEqual(apps.get(second), {})
            with self.assertRaises(ValueError):
                apps.save(first, dict(action='applied', revision=revision(record)))
            stale = revision(record)
            record = apps.save(first, dict(action='edit', draft='TEST PERSON\nUsed Python', reviewed='yes', revision=stale))
            with self.assertRaises(ValueError):
                apps.save(first, dict(action='edit', draft='stale text', revision=stale))
            with self.assertRaises(ValueError):
                apps.save(first, dict(action='applied', revision=revision(record)))
            record = apps.save(first, dict(action='applied', confirmed='yes', revision=revision(record)))
            applied = record['applied_at']
            store.db.close()
            store = Store(path)
            apps = Applications(store)
            self.assertEqual(apps.get(first)['applied_at'], applied)
            record = apps.save(first, dict(action='generate', source='TEST PERSON Python', requirements='Python', revision=revision(record)))
            self.assertFalse(record['reviewed'])
            self.assertEqual(record['applied_at'], applied)
            record = apps.save(first, dict(action='undo', revision=revision(record)))
            self.assertIsNone(record['applied_at'])
            self.assertEqual(apps.get(second), {})
            store.db.close()
