import os
import http.cookiejar
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.parse import urlencode
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import re
import app
from accounts import Accounts
from shortlist import Store
from applications import Applications,revision
from test_shortlist import fixture

class SettingsTests(unittest.TestCase):
 def test_all_settings_remain_saved_and_applied_redirects(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'ROOT',Path(d)/'data'),patch.object(app,'DB',Path(d)/'no-legacy'),patch('runtime.credentials.read',return_value=''):
   server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
   client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
   def post(path,data):return client.open(Request(base+path,data=urlencode(data).encode(),headers={'Origin':base}))
   try:
    html=post('/register',{'token':app.TOKEN,'email':'test@example.com','password':'long-test-password'}).read().decode()
    token=re.search('name="token" value="([^"]+)"',html)[1]
    response=post('/profile',dict(token=token,all_settings='yes',keywords='Python Engineer',location='India',consent='yes',model='gemini-3.5-flash-lite',limit='3',daily_enabled='',resume_context='TEST PERSON\nPython'))
    self.assertIn('/setup',response.url)
    html=client.open(base+'/setup').read().decode();self.assertIn('name="consent" value="yes" checked',html);self.assertIn('Python Engineer',html)
    # Saving only the resume cannot clear saved search preferences or consent.
    post('/profile',dict(token=token,resume_context='TEST PERSON\nUpdated Python'))
    html=client.open(base+'/setup').read().decode();self.assertIn('name="consent" value="yes" checked',html)
    a=Accounts(app.ROOT);uid=a.users()[0][0];store=Store(a.user_db(uid));jid,_=store.add(fixture(title='APPLIED TEST'));apps=Applications(store);r=apps.save(jid,dict(action='generate',source='TEST RESUME',requirements='Python'))
    response=post('/application',dict(token=token,id=jid,revision=revision(r),action='applied',confirmed='yes'))
    self.assertIn('view=applied',response.url);self.assertIn('APPLIED TEST',response.read().decode());self.assertTrue(apps.get(jid)['applied_at'])
    with patch.dict(os.environ,{'AFTARA_MAIL_SENDER_ACCOUNT':'a'*32}),patch('app.credentials.save') as save_secret:
     before=store.profile()
     post('/profile',dict(token=token,daily='yes',report_email='reports@example.com',smtp_host='attacker.example',smtp_user='attacker',smtp_from='attacker@example.com',smtp_password='must-not-save'))
     after=store.profile()
     self.assertEqual(after['report_email'],'reports@example.com')
     for key in ('smtp_host','smtp_user','smtp_from'):self.assertEqual(after.get(key),before.get(key))
     save_secret.assert_not_called()
    saved=store.profile();saved['overleaf_pending']='a'*64;store.profile(saved)
    with patch('app.build') as fallback:
     with self.assertRaises(HTTPError) as error:client.open(base+'/base-pdf')
     self.assertEqual(error.exception.code,400)
     self.assertIn('latest Overleaf upload',error.exception.read().decode())
     fallback.assert_not_called()
    setup=client.open(base+'/setup').read().decode()
    self.assertNotIn('Preview current PDF',setup)
    self.assertIn('previous resume is still saved',setup)
    store.db.close();a.close()
   finally:server.shutdown();server.server_close();thread.join()
