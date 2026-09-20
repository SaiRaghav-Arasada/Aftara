"""Local account-isolated job preparation and LaTeX PDF review."""
import hashlib
import json
import os
from pathlib import Path
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit
from accounts import Accounts
from applications import Applications,revision
import credentials
from daily_reports import Scheduler,validate
from resume_pdf import build,fingerprint
from runtime import finder_for
from shortlist import Store,now
import views
from uploads import form_data
from documents import document_fingerprint, build_record
from overleaf import unpack, save_project, compile_project, pdf_text

ROOT=Path(os.environ.get('LINKEDINAPPLY_DATA',Path(__file__).with_name('data')))
DB=Path(os.environ.get('LINKEDINAPPLY_DB',Path(__file__).with_name('shortlist.sqlite3')))
TOKEN=secrets.token_urlsafe(32)
PUBLIC_ORIGIN=os.environ.get('LINKEDINAPPLY_PUBLIC_ORIGIN','').rstrip('/')

def page(store,message=''):
    return views.dashboard(store,{'email':'Local user','csrf':TOKEN},message)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):
        if args and str(args[0]).startswith('GET /browser-status'):return
        super().log_message(fmt,*args)
    def respond(self,body,status=200,content_type='text/html; charset=utf-8',download=None):
        raw=body if isinstance(body,bytes) else body.encode()
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','SAMEORIGIN');self.send_header('X-Content-Type-Options','nosniff')
        if download:self.send_header('Content-Disposition',f'attachment; filename="{download}"')
        self.end_headers();self.wfile.write(raw)
    def redirect(self,location,cookie=None):
        self.send_response(303);self.send_header('Location',location);self.send_header('Cache-Control','no-store');self.send_header('Content-Length','0')
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers()
    def valid_host(self):return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
    def cookie(self):
        try:
            cookies=SimpleCookie(self.headers.get('Cookie',''));return cookies['li_session'].value if 'li_session' in cookies else ''
        except Exception:return ''
    def account(self,accounts):return accounts.session(self.cookie())
    def do_GET(self):
        if not self.valid_host():return self.respond('Invalid host',403)
        route=urlsplit(self.path);query=parse_qs(route.query)
        if route.path in ('/styles.css','/ui.js'):
            return self.respond(Path(__file__).with_name(route.path[1:]).read_text(),content_type='text/css' if route.path.endswith('.css') else 'text/javascript')
        accounts=Accounts(ROOT,DB)
        try:
            user=self.account(accounts)
            if route.path in ('/login','/register'):
                if user:return self.redirect('/')
                return self.respond(views.auth(TOKEN,register=route.path=='/register'))
            if not user:
                if route.path=='/browser-status':return self.respond('{}',401,'application/json')
                return self.redirect('/login')
            path=accounts.user_db(user['id']);store=Store(path)
            try:
                finder=finder_for(user['id']);status=finder.status()
                if route.path=='/browser-status':return self.respond(json.dumps(status),content_type='application/json')
                if route.path=='/setup':return self.respond(views.setup(store,user,status,{},query.get('message',[''])[0]))
                if route.path=='/linkedin':return self.respond(views.linkedin(user,status))
                if route.path=='/discover':return self.respond(views.discover(store,user,status))
                if route.path=='/':return self.respond(views.dashboard(store,user,view=query.get('view',['all'])[0]))
                if route.path=='/base-pdf':
                    profile=store.profile()
                    if profile.get('overleaf_pending'):raise ValueError('Your latest Overleaf upload has not compiled. The previous resume is not a preview of that upload. Return to setup to resolve the import.')
                    if profile.get('overleaf_project'):pdf,_=compile_project(path.parent,profile['overleaf_project'])
                    else:pdf,_=build(profile.get('resume_context',''),path.parent/'pdfs')
                    return self.respond(pdf.read_bytes(),content_type='application/pdf')
                if route.path in ('/application','/pdf','/resume','/latex','/print'):
                    job_id=int(query.get('id',['0'])[0]);apps=Applications(store);apps.job(job_id);record=apps.get(job_id)
                    if route.path=='/application':return self.respond(views.application(store,user,job_id))
                    if not record:raise ValueError('Prepare a resume first.')
                    if query.get('v') and query['v'][0]!=document_fingerprint(record):raise ValueError('This preview is out of date. Reload the review page.')
                    pdf,tex=build_record(record,path.parent/'pdfs')
                    if route.path=='/latex':return self.respond(tex.read_bytes(),content_type='application/zip' if record.get('overleaf_project') else 'application/x-tex',download=f'resume-{job_id}.zip' if record.get('overleaf_project') else f'resume-{job_id}.tex')
                    return self.respond(pdf.read_bytes(),content_type='application/pdf',download=f'resume-{job_id}.pdf' if route.path=='/resume' else None)
                return self.respond('Not found',404)
            except (ValueError,KeyError) as error:
                return self.respond(views.shell('Needs attention','<section><h1>One thing needs attention</h1><p>'+views.esc(str(error))+'</p><a href="/">Return to review queue</a></section>',user,'review'),400)
            finally:store.db.close()
        finally:accounts.close()
    def do_POST(self):
        if not self.valid_host():return self.respond('Invalid host',403)
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}',PUBLIC_ORIGIN):return self.respond('Invalid origin',403)
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=21_000_000:return self.respond('Invalid request size',413)
            data=form_data(self.headers.get('Content-Type',''),self.rfile.read(size))
        except (ValueError,UnicodeError):return self.respond('Invalid request',400)
        accounts=Accounts(ROOT,DB)
        try:
            if self.path in ('/login','/register'):
                if not secrets.compare_digest(data.pop('token',''),TOKEN):return self.respond('Reload before signing in.',403)
                try:
                    uid=accounts.register(data.get('email',''),data.get('password','')) if self.path=='/register' else accounts.login(data.get('email',''),data.get('password',''))
                    session=accounts.create_session(uid)
                    return self.redirect('/setup',f'li_session={session}; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800'+('; Secure' if PUBLIC_ORIGIN.startswith('https://') else ''))
                except ValueError as error:return self.respond(views.auth(TOKEN,str(error),self.path=='/register'),400)
            user=self.account(accounts)
            if not user:return self.redirect('/login')
            if not secrets.compare_digest(data.pop('token',''),user['csrf']):return self.respond('Reload the page before saving.',403)
            if self.path=='/logout':
                accounts.logout(self.cookie());return self.redirect('/login','li_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
            path=accounts.user_db(user['id']);store=Store(path);finder=finder_for(user['id'])
            try:
                if self.path=='/resume-project':
                    upload=data.get('project')
                    if not upload and data.get('latex_source','').strip():upload={'name':'main.tex','content':data['latex_source'].encode()}
                    if not isinstance(upload,dict):raise ValueError('Choose your Overleaf archive or paste TeX source.')
                    project=save_project(path.parent,unpack(upload['content'],upload['name']),data.get('main_file','').strip())
                    profile=store.profile();profile['overleaf_pending']=project;store.profile(profile)
                    pdf,_=compile_project(path.parent,project)
                    profile.update(overleaf_project=project,resume_context=pdf_text(pdf));profile.pop('overleaf_pending',None);store.profile(profile)
                    return self.redirect('/setup?message=Resume+project+saved.+Your+original+template+is+preserved.')
                if self.path=='/email-test':
                    from daily_reports import test_delivery
                    test_delivery(store,user['id'])
                    return self.redirect('/setup?message=Test+report+accepted+by+your+email+provider.+Check+your+inbox+and+spam.')
                if self.path=='/profile':
                    p=store.profile()
                    if '\\documentclass' in data.get('resume_context',''):raise ValueError('Paste LaTeX in the Overleaf import field above so your original formatting is preserved.')
                    allowed=('resume_context','keywords','location','model','limit','consent','report_email','report_time','timezone','smtp_host','smtp_port','smtp_user','smtp_from')
                    shared_sender=bool(os.environ.get('AFTARA_MAIL_SENDER_ACCOUNT'))
                    p.update({k:v for k,v in data.items() if k in allowed and not (shared_sender and k.startswith('smtp_'))})
                    if p.get('overleaf_project') and 'resume_context' in data:raise ValueError('Use the project upload to update a template-based resume.')
                    if data.get('preferences')=='yes' or data.get('all_settings')=='yes':p['consent']=data.get('consent','')
                    if data.get('daily')=='yes' or data.get('all_settings')=='yes':
                        p['daily_requested']=data.get('daily_enabled','');p['daily_enabled']=''
                        store.profile(p)
                        password='' if shared_sender else data.get('smtp_password','')
                        if password:credentials.save(user['id'],'smtp',password)
                        if p['daily_requested']=='yes':
                            try:
                                from daily_reports import delivery_settings
                                sender,stored_password=delivery_settings(p,user['id'])
                                validate(sender,bool(stored_password));p['daily_enabled']='yes'
                            except ValueError as error:
                                store.profile(p)
                                return self.respond(views.setup(store,user,finder.status(),{},'Settings saved. Daily email is not active yet: '+str(error)),400)
                    store.profile(p);return self.redirect('/setup?message=All+settings+saved.')
                if self.path=='/connection':
                    key=data.get('api_key','').strip()
                    if not key or len(key)>300 or '\n' in key:raise ValueError('Enter a valid Gemini key.')
                    credentials.save(user['id'],'gemini',key)
                    with finder.lock:finder.key=key
                    return self.respond(views.setup(store,user,finder.status(),{},'Key saved securely. You only need to replace it if it changes.'))
                if self.path=='/browser':
                    p=store.profile();finder.submit(data.get('action'),dict(p,consent=p.get('consent','')),path)
                    return self.redirect('/linkedin' if data.get('return_to')=='linkedin' else '/discover')
                if self.path=='/import':store.add(data);return self.redirect('/')
                if self.path in ('/application','/prepare','/approve'):
                    job_id=int(data['id']);apps=Applications(store);job=apps.job(job_id);r=apps.get(job_id)
                    if self.path=='/prepare':
                        if r:raise ValueError('A draft already exists. Open it to edit.')
                        source=store.profile().get('resume_context','')
                        apps.save(job_id,dict(action='generate',source=source,requirements=job.get('skills') or job['title'],revision=''))
                        r=apps.get(job_id)
                        if store.profile().get('overleaf_project'):
                            r.update(overleaf_project=store.profile()['overleaf_project'],overleaf_edits=[])
                            with store.db:store.db.execute('UPDATE applications SET data=? WHERE job_id=?',(json.dumps(r),job_id))
                        build_record(r,path.parent/'pdfs')
                    elif self.path=='/approve':
                        if not r or data.get('revision')!=revision(r) or data.get('pdf_hash')!=document_fingerprint(r):raise ValueError('This resume changed. Review the latest PDF before approving.')
                        if data.get('confirmed')!='yes':raise ValueError('Confirm that you reviewed the PDF.')
                        build_record(r,path.parent/'pdfs');r.update(approved_pdf=document_fingerprint(r),reviewed=True,approved_at=now())
                        with store.db:store.db.execute('UPDATE applications SET data=? WHERE job_id=?',(json.dumps(r),job_id))
                    else:
                        if data.get('action')=='edit' and r.get('overleaf_project'):raise ValueError('Template resumes preserve their TeX source. Upload a revised source project in setup for future drafts.')
                        apps.save(job_id,data)
                        if data.get('action')=='applied':return self.redirect('/?view=applied')
                        if data.get('action')=='edit':build_record(apps.get(job_id),path.parent/'pdfs')
                    return self.redirect(f'/application?id={job_id}')
                return self.respond('Not found',404)
            except (ValueError,KeyError) as error:
                if self.path in ('/profile','/connection','/resume-project','/email-test'):return self.respond(views.setup(store,user,finder.status(),{},str(error)),400)
                if self.path=='/browser':return self.respond(views.discover(store,user,finder.status(),str(error)),400)
                return self.respond(views.dashboard(store,user,str(error)),400)
            finally:store.db.close()
        finally:accounts.close()

if __name__=='__main__':
    port=int(os.environ.get('PORT','8501'))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    Scheduler(ROOT).start()
    print(f'Open http://127.0.0.1:{port} — Ctrl+C to stop',flush=True)
    server.serve_forever()
