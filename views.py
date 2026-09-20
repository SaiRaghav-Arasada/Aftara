import html
import os
from applications import Applications,revision
from browser_jobs import get_assessment
from resume_pdf import fingerprint
from documents import document_fingerprint

def esc(v):return html.escape(str(v),quote=True)
def field(name,label,value='',area=False,kind='text'):
    control=f'<textarea name="{name}" rows="12">{esc(value)}</textarea>' if area else f'<input type="{kind}" name="{name}" value="{esc(value)}">'
    return f'<label>{label}{control}</label>'
def form(action,body,token):return f'<form action="{action}" method="post"><input type="hidden" name="token" value="{token}">{body}</form>'
def select(name,label,options,value):return '<label>'+label+f'<select name="{name}">'+''.join(f'<option value="{esc(k)}" {"selected" if str(k)==str(value) else ""}>{esc(v)}</option>' for k,v in options)+'</select></label>'
def shell(title,body,user,active,message=''):
    nav=''.join(f'<a class="{"active" if key==active else ""}" href="{url}"><span>{i}</span>{label}</a>' for i,key,url,label in [(1,'setup','/setup','Your setup'),(2,'prepare','/discover','Find & prepare'),(3,'review','/','Review applications')])
    logout=form('/logout','<button class="text-button">Sign out</button>',user['csrf'])
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · Aftara</title><link rel="stylesheet" href="/styles.css?v=20260918"></head><body class="workspace"><a class="skip" href="#main">Skip to content</a><header><a class="brand" href="/"><span class="brand-icon">↗</span>Aftara</a><div class="account"><span>{esc(user["email"])}</span>{logout}</div></header><nav aria-label="Main workflow">{nav}</nav><main id="main" class="workspace-main"><div class="toast" role="status">{esc(message)}</div>{body}</main><footer>Your experience. Your voice. Your next chapter. <span class="footer-detail">You review before you apply.</span></footer><script src="/ui.js"></script></body></html>'
def auth(token,message='',register=False):
    title='Make your next move.' if register else 'Good to see you again.'
    fields=field('email','Email address',kind='email')+field('password','Password · at least 12 characters',kind='password')+'<button class="primary wide">'+('Create account →' if register else 'Sign in →')+'</button>'
    story='<aside class="auth-story"><a class="brand" href="/"><span class="brand-icon">↗</span>Aftara</a><div class="story-copy"><p class="eyebrow">Your next chapter, thoughtfully.</p><h2>Your next chapter,<br><em>closer than ever.</em></h2><p>A thoughtful space to find opportunities, shape your resume, and move forward with confidence.</p></div><div class="orbital" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="orbit-core">↗</div><span class="orbit-caption">YOUR NEXT POSSIBILITY</span></div><div class="story-bottom"><span>Find your fit.</span><span>Keep your voice.</span><span>Make your move.</span></div></aside>'
    panel=f'<section class="auth-panel"><div class="auth-form"><p class="eyebrow">YOUR PERSONAL WORKSPACE</p><h1>{title}</h1><p>{"Start with your experience. We’ll help you take the next step." if register else "Your next opportunity is worth coming back for."}</p><p class="error" role="alert">{esc(message)}</p>{form("/register" if register else "/login",fields,token)}<p class="auth-switch">{("Already have an account?" if register else "New to Aftara?")} <a href="{("/login" if register else "/register")}">{("Sign in" if register else "Create an account")}</a></p><div class="auth-note"><span>◇</span><p>Your own workspace. Your saved resume.<br>You review every application before submitting.</p></div></div></section>'
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{"Create account" if register else "Welcome back"} · Aftara</title><link rel="stylesheet" href="/styles.css?v=20260918"></head><body class="auth-page"><main class="auth-experience">{story}{panel}</main></body></html>'
def heading(eyebrow,title,subtitle):return f'<div class="page-heading"><p class="eyebrow">{eyebrow}</p><h1>{esc(title)}</h1><p>{subtitle}</p></div>'
def setup(store,user,status,settings,message=''):
    p=store.profile();token=user['csrf'];has_resume=bool(p.get('resume_context'))
    body=heading('Your foundation','Make this space yours.','Save your preferences together. Your resume and connections stay with your account.')
    body+='<section><h2>1. Your resume</h2>'
    if p.get('overleaf_pending'):
        body+='<p class="notice">Your latest Overleaf upload could not compile. Its PDF is not ready. Your previous resume is still saved; it does not represent this upload.</p>'
    elif p.get('overleaf_project'):
        body+='<p class="success">Original Overleaf template saved. Your layout, fonts and source files are preserved.</p><a class="button" target="_blank" href="/base-pdf">Preview original PDF</a>'
    elif has_resume:body+='<p>Text resume saved. Import an Overleaf project below to preserve its original formatting.</p><a href="/base-pdf" target="_blank">Preview current PDF</a>'

    body+='<details '+('' if has_resume else 'open')+'><summary>Upload your Overleaf project or paste LaTeX</summary><p>Upload .zip, .tar, .tar.gz or .tex (up to 20 MB). Include class files, images and custom fonts. Your template is compiled with Tectonic (XeTeX). Projects requiring another compiler may need adjustments.</p><form action="/resume-project" method="post" enctype="multipart/form-data"><input type="hidden" name="token" value="'+token+'"><label>Overleaf source project<input type="file" name="project" accept=".zip,.tar,.gz,.tgz,.tex"></label>'+field('main_file','Main TeX file · optional if detected automatically')+field('latex_source','Or paste a complete standalone TeX document',area=True)+'<button class="primary">Import & preview original resume</button></form></details></section>'
    body+='<section><h2>2. Gemini connection</h2>'
    if status['key_connected']:body+='<p class="success">Connected. Your saved key is ready to use.</p><details><summary>Replace API key</summary>'
    body+=form('/connection',field('api_key','Gemini API key',kind='password')+'<button>Save key securely</button>',token)
    if status['key_connected']:body+='</details>'
    body+='</section>'
    content='<input type="hidden" name="all_settings" value="yes"><section><h2>3. Job preferences</h2>'
    if not p.get('overleaf_project'):content+='<details><summary>Text resume · uses a standard layout</summary>'+field('resume_context','Resume text',p.get('resume_context',''),True)+'</details>'
    content+=field('keywords','Job titles to search',p.get('keywords','AI Engineer'))+field('location','Location',p.get('location','India'))
    content+=select('model','Low-cost model',[('gemini-3.5-flash-lite','Gemini 3.5 Flash-Lite'),('gemini-3.1-flash-lite','Gemini 3.1 Flash-Lite')],p.get('model','gemini-3.5-flash-lite'))
    content+=select('limit','Jobs to prepare per run',[('1','1 job · testing'),('3','3 jobs'),('5','5 jobs')],p.get('limit','1'))
    content+='<label class="check"><input type="checkbox" name="consent" value="yes" '+('checked' if p.get('consent')=='yes' else '')+'>Allow Gemini to use my resume and job descriptions for matching and factual wording suggestions.</label></section>'
    content+='<section><h2>4. Daily email</h2><p class="'+('success' if p.get('daily_enabled')=='yes' else 'hint')+'">'+('Daily reports are enabled.' if p.get('daily_enabled')=='yes' else 'Daily reports are off. Choose your report email and enable daily delivery.')+'</p>'
    content+='<label class="check"><input type="checkbox" name="daily_enabled" value="yes" '+('checked' if p.get('daily_requested',p.get('daily_enabled'))=='yes' else '')+'>Find jobs daily and email me the results.</label>'
    content+=field('report_email','Send reports to',p.get('report_email',user['email']),kind='email')+field('report_time','Daily delivery time',p.get('report_time','09:00'),kind='time')+select('timezone','Timezone',[('Asia/Kolkata','India'),('UTC','UTC'),('Europe/London','London'),('America/New_York','New York')],p.get('timezone','Asia/Kolkata'))
    if not os.environ.get('AFTARA_MAIL_SENDER_ACCOUNT'):
        content+='<details '+('' if p.get('smtp_host') else 'open')+'><summary>Connect your email sender</summary><p>For Gmail: SMTP server <strong>smtp.gmail.com</strong>, port <strong>465 · TLS</strong>, and your full Gmail address in both sender fields. Enable 2-Step Verification, then create a Google App Password for Aftara. Use that app password here, not your normal Gmail password. <a href="https://support.google.com/mail/answer/185833" target="_blank" rel="noopener">Google’s setup instructions ↗</a></p>'+field('smtp_host','SMTP server',p.get('smtp_host',''))+select('smtp_port','Secure connection',[('465','465 · TLS'),('587','587 · STARTTLS')],p.get('smtp_port','465'))+field('smtp_user','Sender username',p.get('smtp_user',''))+field('smtp_from','Sender email',p.get('smtp_from',''),kind='email')+field('smtp_password','App password · leave blank to keep saved',kind='password')+'</details>'
    else:content+='<p class="hint">Email delivery is managed by Aftara. Just choose where and when your report arrives.</p>'
    content+='<p class="hint">The server must stay running. Reports cover your selected batch and locally recorded application status.</p></section><div class="save-bar"><button class="primary">Save all preferences & email settings</button><span data-save-status>Changes are saved when you press this button.</span></div>'
    body+=form('/profile',content,token)
    body+='<section><h2>Check email delivery</h2><p>Save your preferences, then send yourself a test report. Check your inbox and spam folder.</p>'+form('/email-test','<button>Send me a test report</button>',token)
    if p.get('email_test_at'):body+='<p class="success">Last test accepted by the email provider: '+esc(p['email_test_at'])+'</p>'
    if store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='daily_runs'").fetchone():
        rows=store.db.execute('SELECT day,status,message FROM daily_runs ORDER BY day DESC LIMIT 3').fetchall()
        body+=''.join('<p>'+esc(' · '.join(row))+'</p>' for row in rows)
    body+='</section><a class="button primary" href="/discover">Continue to find jobs →</a>'
    return shell('Your setup',body,user,'setup',message)

def discover(store,user,status,message=''):
    p=store.profile();ready=bool(p.get('resume_context') and p.get('consent')=='yes' and status['key_connected'])
    body=heading('A fresh start','Good opportunities start here.','Use your saved preferences. Review the PDFs when they are ready.')
    body+='<div class="prepare-layout"><section><h2>Your next run</h2><dl><dt>Roles</dt><dd>'+esc(p.get('keywords','Not configured'))+'</dd><dt>Location</dt><dd>'+esc(p.get('location','Not configured'))+'</dd><dt>Model</dt><dd>'+esc(p.get('model','gemini-3.5-flash-lite'))+'</dd><dt>Batch size</dt><dd>'+esc(p.get('limit','1'))+' job(s)</dd></dl><a href="/setup">Change preferences</a>'
    if not ready:body+='<p class="notice">Finish your resume, Gemini key, and consent in setup first.</p><a class="button primary" href="/setup">Finish setup</a>'
    else:body+=form('/browser','<button class="primary wide" name="action" value="search" data-busy-button>Find jobs & prepare resumes</button>',user['csrf'])
    body+='</section><section class="progress-panel"><span class="badge" id="run-badge">'+('Working' if status['busy'] else 'Ready')+'</span><h2>Preparation status</h2><p id="finder-message" role="status">'+esc(status['message'])+'</p><ol class="run-steps"><li>Read job listings</li><li>Assess fit against your resume</li><li>Prepare a factual draft</li><li>Render a PDF for your review</li></ol><a class="button" href="/">Go to review queue →</a></section></div>'
    body+='<section><h2>LinkedIn connection</h2><p>Sign in to LinkedIn once in your private browser. Return here to find jobs.</p><a class="button primary" href="/linkedin">Connect or check LinkedIn</a></section>'
    return shell('Find & prepare',body,user,'prepare',message)
def dashboard(store,user,message='',view='all'):
    apps=Applications(store);jobs=list(reversed(store.jobs()));cards='';counts={'ready':0,'approved':0,'applied':0}
    for j in jobs:
        r=apps.get(j['id']);applied=bool(r.get('applied_at'));approved=r.get('approved_pdf')==document_fingerprint(r)
        state='applied' if applied else 'approved' if approved else 'ready' if r else 'new'
        if state in counts:counts[state]+=1
        if view not in ('all',state):continue
        ai=get_assessment(store,j['id']) or {};label={'applied':'Applied','approved':'PDF approved','ready':'Ready to review','new':'Draft needed'}[state]
        cards+=f'<article class="job"><div class="job-top"><span class="badge {state}">{label}</span><span class="muted">{esc(j.get("location") or "Location not recorded")}</span></div><h2>{esc(j["title"])}</h2><p class="company">{esc(j["company"] or "Company not recorded")}</p><p>{esc(ai.get("reason","Open the listing and review its requirements."))}</p><div class="job-bottom"><a class="button primary" href="/application?id={j["id"]}">{"Review PDF" if r else "Prepare resume"}</a><a href="{esc(j["link"])}" target="_blank" rel="noopener">Original job ↗</a></div></article>'
    body=heading('Step 3 · Your decision','Review applications','Check the job, resume PDF, and wording changes together. Nothing is submitted by approving a PDF.')
    body+='<div class="metrics">'+''.join(f'<div><strong>{counts[k]}</strong><span>{label}</span></div>' for k,label in [('ready','Ready to review'),('approved','PDF approved'),('applied','Applied')])+'</div>'
    body+='<div class="tabs">'+''.join(f'<a class="{"active" if view==k else ""}" href="/?view={k}">{v}</a>' for k,v in [('all','All jobs'),('ready','Ready to review'),('approved','Approved'),('applied','Applied')])+'</div>'
    body+='<div class="job-grid">'+cards+'</div>' if cards else '<section class="empty"><span class="empty-icon">↗</span><h2>'+('No jobs in this view' if jobs else 'Your first application starts here')+'</h2><p>Find a suitable role, then review its tailored resume here.</p><a class="button primary" href="/discover">Find & prepare</a></section>'
    importer=field('title','Job title')+field('company','Company')+field('link','Original job URL',kind='url')+field('description','Job description',area=True)+'<input type="hidden" name="status" value="unknown"><button class="primary">Add job</button>'
    body+='<details class="support"><summary>Add a job yourself</summary>'+form('/import',importer,user['csrf'])+'</details>'
    return shell('Review applications',body,user,'review',message)
def application(store,user,job_id,message=''):
    apps=Applications(store);j=apps.job(job_id);r=apps.get(job_id);token=user['csrf'];rev=revision(r) if r else ''
    hidden=f'<input type="hidden" name="id" value="{job_id}"><input type="hidden" name="revision" value="{rev}">'
    body='<a class="back" href="/">← Review queue</a>'+heading('Application review',j['title'],esc(j['company']))
    if not r:
        body+='<section><h2>Prepare a PDF from your saved resume</h2><p>Your base resume is already saved. Prepare a document to review for this job.</p>'+form('/prepare',hidden+'<button class="primary">Prepare resume PDF</button>',token)+'</section>'
        return shell('Prepare resume',body,user,'review',message)
    pdfhash=document_fingerprint(r);approved=r.get('approved_pdf')==pdfhash
    body+='<div class="review-layout"><section class="pdf-panel"><div class="pdf-toolbar"><h2>Resume PDF</h2><a class="button" href="/resume?id='+str(job_id)+'">Download PDF</a></div><iframe title="LaTeX-rendered resume PDF" src="/pdf?id='+str(job_id)+'&amp;v='+pdfhash+'"></iframe><p class="hint">Rendered with LaTeX. This is the PDF you are reviewing.</p></section><aside class="review-actions"><section><span class="badge '+('approved' if approved else 'ready')+'">'+('PDF approved' if approved else 'Awaiting your review')+'</span><h2>Check before approving</h2><p>Confirm the wording is accurate and the PDF looks right.</p>'
    if approved:body+='<p class="success">This exact PDF is approved. Editing the resume removes approval.</p>'
    else:body+=form('/approve',hidden+'<input type="hidden" name="pdf_hash" value="'+pdfhash+'"><label class="check"><input type="checkbox" name="confirmed" value="yes" required>I reviewed this PDF and confirm its claims are accurate.</label><button class="primary wide">Approve this PDF</button>',token)
    body+='<p class="hint">PDF approval does not submit an application. Automatic submission and direct Overleaf editing remain unavailable.</p><a href="'+esc(j['link'])+'" target="_blank" rel="noopener">Open job application ↗</a></section>'
    ai=get_assessment(store,job_id) or {}
    body+='<section><h2>Job fit</h2><p>'+esc(ai.get('reason','No AI assessment is available for this job.'))+'</p><h3>Gaps to check</h3><ul>'+''.join('<li>'+esc(x)+'</li>' for x in ai.get('gaps',r.get('missing',[])))+'</ul></section></aside></div>'
    edits=r.get('rewrite_evidence',[])
    body+='<details class="support"><summary>Review proposed AI wording changes ('+str(len(edits))+')</summary>'+(''.join('<div class="diff"><p><b>Original</b><br>'+esc(e['original'])+'</p><p><b>AI proposal (before manual edits)</b><br>'+esc(e['replacement'])+'</p></div>' for e in edits) or '<p>No AI wording changes recorded. Check any manual edits against your original resume.</p>')+'</details>'
    if not r.get('overleaf_project'):
        body+='<details class="support"><summary>Edit resume wording</summary>'+form('/application',hidden+field('draft','Resume content',r['draft'],True)+'<button name="action" value="edit" class="primary">Save changes & rebuild PDF</button>',token)+'</details>'
    body+='<section class="application-status"><h2>Application status</h2><p>'+('You marked this job as applied.' if r.get('applied_at') else 'Opening the job or approving a PDF does not record submission. After submitting on LinkedIn or the employer’s site, mark it here.')+'</p>'+form('/application',hidden+('<button name="action" value="undo">Undo applied status</button>' if r.get('applied_at') else '<label class="check"><input type="checkbox" name="confirmed" value="yes" required>I submitted this application on the job website.</label><button name="action" value="applied" class="primary">Mark as applied</button>'),token)+'</section>'
    body+='<details class="support"><summary>Download source files</summary><a href="/latex?id='+str(job_id)+'">'+('Download original-template project ZIP' if r.get('overleaf_project') else 'Download generated LaTeX source')+'</a></details>'
    if r.get('overleaf_project'):body+='<p class="hint">Original Overleaf template preserved. '+str(len(r.get('overleaf_edits',[])))+' wording change(s) mapped to source. Unmatched suggestions were not applied.</p>'
    return shell('Review resume PDF',body,user,'review',message)


def linkedin(user,status):
    body=heading('LinkedIn connection','Sign in to your LinkedIn account','This private browser runs on your server. Only your signed-in app account can open it.')
    body+='<section>'+form('/browser','<input type="hidden" name="return_to" value="linkedin"><button class="primary" name="action" value="open">Open LinkedIn sign-in</button><button name="action" value="disconnect">Close connection</button>',user['csrf'])+'<p id="finder-message">'+esc(status['message'])+'</p><span id="run-badge" hidden></span></section>'
    if status['browser_open']:body+='<iframe class="linkedin-frame" title="Your private LinkedIn sign-in browser" src="/remote/vnc_lite.html?autoconnect=true&amp;resize=scale&amp;path=remote/websockify"></iframe>'
    else:body+='<section><p>Press Open LinkedIn sign-in. Your private browser will appear here when ready.</p></section>'
    body+='<a class="button primary" href="/discover">I’m signed in · Continue to find jobs →</a>'
    return shell('Connect LinkedIn',body,user,'prepare')
