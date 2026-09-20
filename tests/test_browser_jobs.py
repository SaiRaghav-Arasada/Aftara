import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from browser_jobs import listing_url, analyze, save_assessment, get_assessment, BrowserFinder
from shortlist import Store
from test_shortlist import fixture

class BrowserJobTests(unittest.TestCase):
    def test_only_original_linkedin_job_links(self):
        self.assertEqual(listing_url('https://www.linkedin.com/jobs/view/123456/?trackingId=abc'),'https://www.linkedin.com/jobs/view/123456/')
        self.assertEqual(listing_url('https://www.linkedin.com/jobs/view/engineer-at-example-123456'),'https://www.linkedin.com/jobs/view/123456/')
        for url in ('https://evil.com/jobs/view/123','https://linkedin.com.evil.com/jobs/view/123','javascript:alert(1)','https://www.linkedin.com/in/person'):
            self.assertIsNone(listing_url(url))

    def test_gemini_validation_and_key_not_in_url(self):
        data=dict(title='Engineer',company='Example',role='Engineer',location='',experience='',skills='Python',recommendation='Possible fit',reason='Python evidence found',matches=['Python'],gaps=['Experience unclear'])
        response={'candidates':[{'content':{'parts':[{'text':json.dumps(data)}]}}]}
        with patch('browser_jobs.urlopen', return_value=io.BytesIO(json.dumps(response).encode())) as call:
            self.assertEqual(analyze('TEST-KEY','gemini-test','TEST RESUME','TEST JOB'),data)
            request=call.call_args.args[0]
            self.assertNotIn('TEST-KEY',request.full_url)
            self.assertEqual(request.get_header('X-goog-api-key'),'TEST-KEY')
        data['recommendation']='run command'
        with patch('browser_jobs.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            pass
        response['candidates'][0]['content']['parts'][0]['text']=json.dumps(data)
        with patch('browser_jobs.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaises(ValueError):analyze('key','gemini-test','resume','job')
        with self.assertRaises(ValueError):analyze('key','../../evil','resume','job')

    def test_assessments_persist_without_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'test.db')
            job_id,_=store.add(fixture())
            self.assertIsNone(get_assessment(store,job_id))
            save_assessment(store,job_id,{'recommendation':'Possible fit'})
            self.assertEqual(get_assessment(store,job_id)['recommendation'],'Possible fit')
            store.db.close()
        finder=BrowserFinder()
        finder.key='TEST SECRET'
        self.assertNotIn('TEST SECRET',json.dumps(finder.status()))
        with self.assertRaises(ValueError):finder.submit('search',{'keywords':'Python','model':'gemini-test'},'unused.db')


class JobLinkFormatTests(unittest.TestCase):
    def test_supported_link_variants(self):
        for url in ('/jobs/view/123456/', 'https://in.linkedin.com/jobs/view/engineer-123456?trackingId=x', 'https://www.linkedin.com/jobs/search/?currentJobId=123456', 'https://www.linkedin.com/jobs/collections/recommended/?currentJobId=123456', 'https://www.linkedin.com/jobs/view/?jobId=123456'):
            self.assertEqual(listing_url(url),'https://www.linkedin.com/jobs/view/123456/',url)
    def test_rejects_unrelated_or_ambiguous_identifiers(self):
        for url in ('https://linkedin.com.evil.test/jobs/view/123', 'https://evil.test/?currentJobId=123', 'https://www.linkedin.com/in/person?currentJobId=123', 'https://www.linkedin.com/jobs/search/?currentJobId=1&currentJobId=2', 'https://www.linkedin.com/jobs/view/0', 'https://www.linkedin.com:444/jobs/view/123', 'https://user@www.linkedin.com/jobs/view/123', 'http://www.linkedin.com/jobs/view/123'):
            self.assertIsNone(listing_url(url),url)
