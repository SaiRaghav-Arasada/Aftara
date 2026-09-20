from pathlib import Path
import tempfile
import unittest
from accounts import Accounts
from shortlist import Store
from resume_pdf import source
from daily_reports import validate
class AccountTests(unittest.TestCase):
 def test_passwords_sessions_and_owner_migration(self):
  with tempfile.TemporaryDirectory() as d:
   legacy=Path(d)/'legacy.db';s=Store(legacy);s.profile({'resume_context':'OWNER RESUME'});s.db.close();a=Accounts(Path(d)/'data',legacy)
   uid=a.register('Owner@example.com','a-long-password!');uid2=a.register('second@example.com','another-long-password!')
   self.assertEqual(a.login('owner@example.com','a-long-password!'),uid)
   with self.assertRaises(ValueError):a.login('owner@example.com','wrong')
   token=a.create_session(uid);self.assertEqual(a.session(token)['id'],uid);a.logout(token);self.assertIsNone(a.session(token))
   one=Store(a.user_db(uid));two=Store(a.user_db(uid2));self.assertEqual(one.profile()['resume_context'],'OWNER RESUME');self.assertNotIn('resume_context',two.profile())
   one.db.close();two.db.close();a.close()
 def test_latex_escaping_and_sender_required(self):
  tex=source('TEST PERSON\nEXPERIENCE\n• Built 20% of A&B with \\input{secret}')
  self.assertIn(r'20\%',tex);self.assertNotIn(r'\input{secret}',tex);self.assertIn(r'\textbackslash{}input\{secret\}',tex)
  with self.assertRaises(ValueError):validate({'report_email':'me@example.com'},False)
