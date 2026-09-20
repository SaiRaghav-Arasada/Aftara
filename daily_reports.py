"""Account-scoped daily runs and authenticated TLS email delivery."""
from datetime import datetime
import os
from email.message import EmailMessage
import ipaddress
import re
import smtplib
import socket
import ssl
import threading
import time
from zoneinfo import ZoneInfo
from accounts import Accounts
from applications import Applications
from browser_jobs import get_assessment
from shortlist import Store
from runtime import finder_for
import credentials

def delivery_settings(profile,uid):
    """Resolve the administrator-owned sender without exposing it in consumer profiles."""
    sender=os.environ.get('AFTARA_MAIL_SENDER_ACCOUNT','')
    if not sender:return dict(profile),credentials.read(uid,'smtp')
    if not re.fullmatch('[a-f0-9]{32}',sender):raise ValueError('The report sender needs administrator attention.')
    from pathlib import Path
    source=Store(Path(os.environ['LINKEDINAPPLY_DATA'])/'users'/sender/'shortlist.sqlite3')
    try:admin=source.profile()
    finally:source.db.close()
    settings=dict(profile)
    for key in ('smtp_host','smtp_port','smtp_user','smtp_from'):settings[key]=admin.get(key,'')
    return settings,credentials.read(sender,'smtp')

def email_address(value):
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value or ''):raise ValueError('Enter a valid email address.')
    return value

def validate(p,password_saved):
    email_address(p.get('report_email',''));email_address(p.get('smtp_from',''))
    if not p.get('smtp_host') or not p.get('smtp_user') or not password_saved:raise ValueError('Connect an email sender before enabling daily reports.')
    if p.get('smtp_port') not in ('465','587'):raise ValueError('Use SMTP port 465 or 587.')
    if not re.fullmatch(r'\d{2}:\d{2}',p.get('report_time','')):raise ValueError('Choose a daily report time.')
    datetime.strptime(p['report_time'],'%H:%M');ZoneInfo(p.get('timezone','Asia/Kolkata'))

def digest(store,run_message):
    from documents import document_fingerprint
    apps=Applications(store);rows=[]
    for job in reversed(store.jobs()[-50:]):
        r=apps.get(job['id']);ai=get_assessment(store,job['id']) or {}
        status='Applied' if r.get('applied_at') else 'PDF approved' if r and r.get('approved_pdf')==document_fingerprint(r) else 'Draft ready for review' if r else 'No draft yet'
        rows.append(f"{job['title']} — {job['company']}\nStatus: {status}\nFit: {ai.get('recommendation','Not assessed')}\n{ai.get('reason','')}\nGaps: {'; '.join(ai.get('gaps',[])) or 'None recorded'}\nListing: {job['link']}\n")
    return 'Your daily Aftara report\n\nRun status: '+run_message+'\n\n'+('\n'.join(rows) or 'No jobs have been imported yet.')+'\n\nReview your applications: '+os.environ.get('LINKEDINAPPLY_PUBLIC_ORIGIN','http://127.0.0.1:8501')+'/?view=ready\nNo applications were submitted automatically.'

def digest_html(store,run_message):
    from email_template import render_report
    from documents import document_fingerprint
    apps=Applications(store);rows=[]
    for job in reversed(store.jobs()[-50:]):
        r=apps.get(job['id']);ai=get_assessment(store,job['id']) or {}
        status='Applied' if r.get('applied_at') else 'PDF approved' if r and r.get('approved_pdf')==document_fingerprint(r) else 'Ready to review' if r else 'No draft yet'
        rows.append(dict(id=job['id'],title=job['title'],company=job['company'],link=job['link'],status=status,fit=ai.get('recommendation','Not assessed'),reason=ai.get('reason',''),gaps='; '.join(ai.get('gaps',[])) or 'None recorded'))
    return render_report(rows,run_message,os.environ.get('LINKEDINAPPLY_PUBLIC_ORIGIN','http://127.0.0.1:8501'))

def send(p,password,text,html=None):
    host=p['smtp_host'].strip()
    if any(ipaddress.ip_address(r[4][0]).is_private or ipaddress.ip_address(r[4][0]).is_loopback for r in socket.getaddrinfo(host,None)):
        raise ValueError('Use your email provider’s public SMTP host.')
    msg=EmailMessage();msg['Subject']='Your daily job matches & application status';msg['From']=email_address(p['smtp_from']);msg['To']=email_address(p['report_email']);msg.set_content(text)
    if html:msg.add_alternative(html,subtype='html')
    if p['smtp_port']=='465':
        client=smtplib.SMTP_SSL(host,465,context=ssl.create_default_context(),timeout=30)
    else:
        client=smtplib.SMTP(host,587,timeout=30);client.ehlo();client.starttls(context=ssl.create_default_context());client.ehlo()
    with client:
        client.login(p['smtp_user'],password);client.send_message(msg)

class Scheduler:
    def __init__(self,root):self.root=root;self.running=set();self.lock=threading.Lock()
    def start(self):threading.Thread(target=self.loop,daemon=True).start()
    def loop(self):
        while True:
            try:
                accounts=Accounts(self.root)
                try:
                    for uid,email in accounts.users():
                        path=accounts.user_db(uid);store=Store(path)
                        try:
                            p=store.profile()
                            if p.get('daily_enabled')!='yes':continue
                            local=datetime.now(ZoneInfo(p.get('timezone','Asia/Kolkata')))
                            date=local.date().isoformat()
                            if local.strftime('%H:%M')<p.get('report_time','09:00'):continue
                            store.db.execute('CREATE TABLE IF NOT EXISTS daily_runs (day TEXT PRIMARY KEY,status TEXT,message TEXT)');store.db.commit()
                            if store.db.execute('SELECT 1 FROM daily_runs WHERE day=?',(date,)).fetchone():continue
                            with self.lock:
                                if uid in self.running:continue
                                self.running.add(uid)
                            with store.db:store.db.execute('INSERT INTO daily_runs VALUES (?,?,?)',(date,'running','Daily preparation started'))
                            threading.Thread(target=self.run,args=(uid,path,p,date),daemon=True).start()
                        finally:store.db.close()
                finally:accounts.close()
            except Exception:pass
            time.sleep(30)
    def run(self,uid,path,p,date):
        store=Store(path)
        try:
            finder=finder_for(uid)
            try:
                if finder.status()['busy']:raise ValueError('A manual search is still running. This report includes the jobs already available.')
                finder.submit('search',dict(p,consent=p.get('consent','')),path)
                until=time.monotonic()+900
                while finder.status()['busy'] and time.monotonic()<until:time.sleep(2)
                status=finder.status()
                message=('Job preparation is still running. This report includes the jobs already available.' if status['busy'] else status['message'])
            except ValueError as error:message=str(error)
            sender,password=delivery_settings(p,uid);validate(sender,bool(password));send(sender,password,digest(store,message),digest_html(store,message))
            with store.db:store.db.execute('UPDATE daily_runs SET status=?,message=? WHERE day=?',('sent','Email provider accepted the report. '+message,date))
        except Exception:
            with store.db:store.db.execute('UPDATE daily_runs SET status=?,message=? WHERE day=?',('failed','Daily report failed. Check your browser session and email sender settings.',date))
        finally:
            store.db.close()
            with self.lock:self.running.discard(uid)


def test_delivery(store,uid):
    p=store.profile();sender,password=delivery_settings(p,uid);validate(sender,bool(password))
    try:send(sender,password,digest(store,'Test report requested from your account settings.'),digest_html(store,'Test report requested from your account settings.'))
    except smtplib.SMTPAuthenticationError:raise ValueError('The report email connection needs administrator attention.' if os.environ.get('AFTARA_MAIL_SENDER_ACCOUNT') else 'Email sign-in failed. Check the sender username and app password.') from None
    except (smtplib.SMTPException,OSError):raise ValueError('The email provider could not accept the report. Check SMTP host, port, sender and recipient.') from None
    p['email_test_at']=datetime.now().isoformat();store.profile(p)
