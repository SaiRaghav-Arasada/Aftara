import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from shortlist import Store
from test_shortlist import fixture
from daily_reports import digest, send

class DailyReportTests(unittest.TestCase):
 def test_jobs_without_drafts_are_reported(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(Path(d)/'jobs.db');store.add(fixture(title='REPORT TEST JOB'))
   result=digest(store,'Sign in required')
   self.assertIn('REPORT TEST JOB',result);self.assertIn('No draft yet',result);self.assertIn('Sign in required',result)
   store.db.close()
 def test_tls_delivery_uses_configured_recipient(self):
  settings=dict(smtp_host='smtp.example.com',smtp_port='465',smtp_from='sender@example.com',report_email='recipient@example.com',smtp_user='sender')
  with patch('daily_reports.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',0))]),patch('daily_reports.smtplib.SMTP_SSL') as smtp:
   send(settings,'TEST-ONLY','TEST REPORT')
   smtp.return_value.login.assert_called_once_with('sender','TEST-ONLY')
   msg=smtp.return_value.send_message.call_args.args[0]
   self.assertEqual(msg['To'],'recipient@example.com');self.assertIn('TEST REPORT',msg.get_content())

 def test_busy_search_still_sends_daily_report(self):
  from daily_reports import Scheduler
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'jobs.db';store=Store(path)
   store.db.execute('CREATE TABLE daily_runs (day TEXT PRIMARY KEY,status TEXT,message TEXT)')
   store.db.execute("INSERT INTO daily_runs VALUES ('2026-09-15','running','')");store.db.commit();store.db.close()
   finder=MagicMock();finder.status.return_value={'busy':True}
   scheduler=Scheduler(Path(d));scheduler.running.add(1)
   with patch('daily_reports.finder_for',return_value=finder),patch('daily_reports.credentials.read',return_value='test'),patch('daily_reports.validate'),patch('daily_reports.send') as sender:
    scheduler.run(1,path,{},'2026-09-15')
    sender.assert_called_once();self.assertIn('manual search is still running',sender.call_args.args[2]);finder.submit.assert_not_called()
   store=Store(path);self.assertEqual(store.db.execute('SELECT status FROM daily_runs').fetchone()[0],'sent');store.db.close()
   self.assertNotIn(1,scheduler.running)

 def test_html_table_escapes_content_and_blocks_unsafe_links(self):
  from email_template import render_report
  result=render_report([dict(id=1,title='<script>bad</script>',company='A & B',link='javascript:alert(1)',status='Ready to review',fit='Potential match',reason='Fits Python',gaps='SQL')],'<b>Update</b>','https://example.com')
  self.assertIn('<table',result);self.assertIn('&lt;script&gt;',result);self.assertNotIn('javascript:',result)
  self.assertIn('https://example.com/application?id=1',result);self.assertIn('&lt;b&gt;Update&lt;/b&gt;',result)

 def test_multipart_message_contains_html_and_plain_text(self):
  settings=dict(smtp_host='smtp.example.com',smtp_port='465',smtp_from='sender@example.com',report_email='recipient@example.com',smtp_user='sender')
  with patch('daily_reports.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',0))]),patch('daily_reports.smtplib.SMTP_SSL') as smtp:
   send(settings,'TEST-ONLY','Plain report','<html><body><table><tr><td>Report</td></tr></table></body></html>')
   msg=smtp.return_value.send_message.call_args.args[0]
   self.assertEqual(msg.get_content_type(),'multipart/alternative')
   self.assertIn('Plain report',msg.get_body(preferencelist=('plain',)).get_content())
   self.assertIn('<table>',msg.get_body(preferencelist=('html',)).get_content())

 def test_shared_sender_ignores_consumer_smtp_and_hides_fields(self):
  import os
  from daily_reports import delivery_settings
  from views import setup
  with tempfile.TemporaryDirectory() as d:
   uid='a'*32;root=Path(d);folder=root/'users'/uid;folder.mkdir(parents=True)
   owner=Store(folder/'shortlist.sqlite3');owner.profile(dict(smtp_host='smtp.example.com',smtp_port='465',smtp_user='private@example.com',smtp_from='private@example.com'));owner.db.close()
   consumer=Store(root/'consumer.db');consumer.profile(dict(report_email='reader@example.com',smtp_user='ATTACKER',smtp_host='ATTACKER'))
   with patch.dict(os.environ,{'AFTARA_MAIL_SENDER_ACCOUNT':uid,'LINKEDINAPPLY_DATA':d}),patch('daily_reports.credentials.read',return_value='SECRET') as secret:
    settings,password=delivery_settings(consumer.profile(),'b'*32)
    self.assertEqual(settings['smtp_user'],'private@example.com');self.assertEqual(settings['report_email'],'reader@example.com');self.assertEqual(password,'SECRET');secret.assert_called_once_with(uid,'smtp')
    page=setup(consumer,{'email':'reader@example.com','csrf':'test'},dict(key_connected=False),{})
    self.assertNotIn('name="smtp_',page);self.assertNotIn('SECRET',page);self.assertNotIn('private@example.com',page);self.assertIn('managed by Aftara',page)
   consumer.db.close()
