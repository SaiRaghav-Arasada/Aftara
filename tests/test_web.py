import http.cookiejar
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer
import app
from accounts import Accounts
from shortlist import Store
from applications import Applications,revision
from resume_pdf import fingerprint
from test_shortlist import fixture

class AccountWorkflowTests(unittest.TestCase):
 def test_isolation_pdf_download_and_approval(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'ROOT',Path(d)/'data'),patch.object(app,'DB',Path(d)/'legacy.db'),patch('runtime.credentials.read',return_value=''):
   server=ThreadingHTTPServer(('127.0.0.1',0),app.Handler);t=threading.Thread(target=server.serve_forever,daemon=True);t.start();base=f'http://127.0.0.1:{server.server_port}'
   def post(c,path,data):
    try:
     with c.open(Request(base+path,data=urlencode(data).encode(),headers={'Origin':base})) as r:return r.status,r.read().decode()
    except HTTPError as e:return e.code,e.read().decode()
   try:
    first=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()));second=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    for c,email in [(first,'first@example.com'),(second,'second@example.com')]:
     self.assertEqual(post(c,'/register',dict(token=app.TOKEN,email=email,password='long-password-123'))[0],200)
    a=Accounts(app.ROOT);users={email:uid for uid,email in a.users()};store=Store(a.user_db(users['first@example.com']))
    jid,_=store.add(fixture(title='PRIVATE TEST JOB'));apps=Applications(store);r=apps.save(jid,dict(action='generate',source='TEST PERSON\nPython engineer',requirements='Python'))
    body=first.open(base+'/application?id=1').read().decode();self.assertIn('PRIVATE TEST JOB',body)
    with self.assertRaises(HTTPError) as error:second.open(base+'/application?id=1')
    self.assertEqual(error.exception.code,400)
    token=__import__('re').search('name="token" value="([^"]+)"',body)[1]
    pdf=Path(d)/'resume.pdf';pdf.write_bytes(b'%PDF-1.4\nTEST');tex=Path(d)/'resume.tex';tex.write_text('TEST')
    with patch.object(app,'build_record',return_value=(pdf,tex)):
     self.assertEqual(post(first,'/approve',dict(token=token,id=jid,revision=revision(r),pdf_hash=fingerprint(r['draft']),confirmed='yes'))[0],200)
     r=apps.get(jid);self.assertEqual(r['approved_pdf'],fingerprint(r['draft']))
     with first.open(base+'/resume?id=1') as response:self.assertEqual(response.headers['Content-Type'],'application/pdf');self.assertIn('.pdf',response.headers['Content-Disposition'])
     self.assertEqual(post(first,'/application',dict(token=token,id=jid,revision=revision(r),action='edit',draft='TEST PERSON\nRevised Python work'))[0],200)
     self.assertNotIn('approved_pdf',apps.get(jid))
     self.assertEqual(post(first,'/approve',dict(token=token,id=jid,revision=revision(r),pdf_hash=fingerprint(r['draft']),confirmed='yes'))[0],400)
    self.assertEqual(post(first,'/profile',dict(token='wrong',resume_context='bad'))[0],403)
    store.db.close();a.close()
   finally:server.shutdown();server.server_close();t.join()
