import tempfile
import unittest
from pathlib import Path
from shortlist import Store, assess, normalize


def fixture(**updates):
    return dict(dict(title='TEST FIXTURE Python Engineer', company='Example Test Company', description='TEST ONLY: Python development', link='https://example.com/jobs/1?utm_source=test', status='unknown'), **updates)

class WorkflowTests(unittest.TestCase):
    def test_links_and_normalization(self):
        self.assertEqual(normalize(fixture())['link'], fixture()['link'])
        for link in ('javascript:alert(1)', 'file:///etc/passwd', 'https://user:pass@example.com'):
            with self.assertRaises(ValueError): normalize(fixture(link=link))

    def test_must_haves_and_unknown_legitimacy(self):
        job = normalize(fixture())
        result = assess(job, {'must_location':'remote', 'must_skills':'python'})
        self.assertEqual(result['eligibility'], 'Needs review')
        self.assertEqual(result['legitimacy'], 'Insufficient evidence')
        self.assertTrue(result['gaps'])
        job.update(location='remote', skills='python')
        self.assertEqual(assess(job, {'must_location':'remote', 'must_skills':'python'})['eligibility'], 'Potential match')
        job['skills'] = 'Java'
        self.assertEqual(assess(job, {'must_skills':'python'})['eligibility'], 'Needs review')
        self.assertEqual(assess(job, {'exclusions':'python'})['eligibility'], 'Excluded')
        job['status'] = 'closed'
        self.assertEqual(assess(job, {})['eligibility'], 'Excluded')

    def test_evidence_is_not_verification(self):
        job = normalize(fixture(evidence_link='https://example.com/careers', evidence_notes='User observation'))
        self.assertEqual(assess(job, {})['legitimacy'], 'Unverified evidence supplied')
        job['concerns'] = 'Company names disagree'
        self.assertEqual(assess(job, {})['legitimacy'], 'Concerns reported')

    def test_persistence_dedup_and_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.sqlite3'
            store = Store(path)
            first, added = store.add(fixture())
            self.assertTrue(added)
            store.state(first, 'saved')
            self.assertEqual(store.add(fixture(link='https://example.com/jobs/1?trk=abc')), (first, False))
            second, _ = store.add(fixture(link='https://example.com/jobs/2'))
            store.profile({'must_skills':'python', 'resume_context':'TEST ONLY'})
            store.state(first, 'selected')
            store.state(second, 'selected')
            store.db.close()
            reopened = Store(path)
            self.assertEqual(reopened.handoff()['selected_job']['id'], second)
            self.assertEqual(reopened.profile()['must_skills'], 'python')
            self.assertEqual(reopened.jobs()[0]['state'], 'saved')
            reopened.state(second, 'dismissed')
            self.assertIsNone(reopened.handoff()['selected_job'])
            reopened.db.close()

if __name__ == '__main__': unittest.main()
