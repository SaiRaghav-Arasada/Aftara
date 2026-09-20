"""Typeset escaped resume content with local LaTeX. Never compiles user-supplied commands."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading

_LOCK=threading.Lock()
VERSION='resume-v2'
SECTIONS={'WORK EXPERIENCE','EXPERIENCE','SKILLS','EDUCATION','AWARDS','PATENTS AND PUBLICATIONS','PUBLICATIONS','PROJECTS','PERSONAL','SUMMARY','CERTIFICATIONS'}

def escape(text):
    replacements={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    return ''.join(replacements.get(c,c) for c in text.replace('ₙ','n').replace('–','-').replace('—','-'))

def source(text):
    lines=[v.strip() for v in text.splitlines() if v.strip()]
    if not lines:raise ValueError('Save a resume before building the PDF.')
    # Earlier drafts prepend duplicated excerpts; the source itself remains intact below them.
    if lines[0].startswith('RELEVANT EXPERIENCE') and '\n\n' in text:
        lines=[v.strip() for v in text.split('\n\n',1)[1].splitlines() if v.strip()]
    body=[r'{\LARGE\bfseries '+escape(lines[0])+r'}\par\vspace{5pt}']
    section=False;bullet=False;section_name="";first_line=False
    for line in lines[1:]:
        if line.upper() in SECTIONS:
            if bullet:body.append(r'\end{itemize}');bullet=False
            section=True;section_name=line.upper();first_line=True
            body.append(r"\needspace{12\baselineskip}" if section_name=="AWARDS" else r"\needspace{5\baselineskip}")
            body.append(r'\section*{'+escape(line.title())+'}')
        elif line.startswith(('• ','- ')):
            if not bullet:body.append(r'\begin{itemize}');bullet=True
            body.append(r'\item '+escape(line[2:]))
        else:
            if bullet:body.append(r'\end{itemize}');bullet=False
            style=r'\small ' if not section else (r'\bfseries ' if first_line or (section_name=='WORK EXPERIENCE' and len(line)<50 and ',' not in line and '|' not in line) else '')
            first_line=False
            body.append('{'+style+escape(line)+r'}\par\vspace{2pt}')
    if bullet:body.append(r'\end{itemize}')
    return r'''\documentclass[10pt,a4paper]{article}
\usepackage[margin=17mm]{geometry}
\usepackage{fontspec}
\setmainfont{texgyreheros-regular.otf}[BoldFont=texgyreheros-bold.otf,ItalicFont=texgyreheros-italic.otf,BoldItalicFont=texgyreheros-bolditalic.otf]
\usepackage{xcolor}
\definecolor{ink}{HTML}{173149}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{needspace}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}
\fancyfoot[R]{\small\color{gray}\thepage}
\setlength{\parindent}{0pt}
\setlength{\parskip}{2pt}
\setlength{\emergencystretch}{3em}
\setlist[itemize]{leftmargin=13pt,itemsep=3pt,topsep=3pt,parsep=0pt}
\titleformat{\section}{\normalsize\bfseries\color{ink}}{}{0pt}{}[\vspace{-3pt}\titlerule]
\titlespacing*{\section}{0pt}{11pt}{6pt}
\widowpenalty=10000\clubpenalty=10000
\begin{document}
'''+ '\n'.join(body)+ '\n\\end{document}\n'

def fingerprint(text):return hashlib.sha256((VERSION+'\n'+text).encode()).hexdigest()

def build(text, root):
    root=Path(root); root.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=root/fingerprint(text); pdf=target/'resume.pdf'
    if pdf.exists():return pdf,target/'resume.tex'
    binary=Path(os.environ.get('LINKEDINAPPLY_TECTONIC',Path(__file__).with_name('bin')/'tectonic'))
    if not binary.exists():raise ValueError('The LaTeX renderer is missing. Install the bundled Tectonic renderer.')
    with _LOCK:
        if pdf.exists():return pdf,target/'resume.tex'
        with tempfile.TemporaryDirectory(dir=root) as directory:
            folder=Path(directory);tex=folder/'resume.tex';tex.write_text(source(text))
            env=dict(os.environ)
            cache=Path(os.environ.get('LINKEDINAPPLY_LATEX_CACHE',Path(__file__).with_name('latex-cache')));cache.mkdir(exist_ok=True)
            env['TECTONIC_CACHE_DIR']=str(cache.resolve())
            try:
                run=subprocess.run([str(binary.resolve()),'--untrusted','--keep-logs','--outdir',str(folder.resolve()),str(tex.resolve())],capture_output=True,timeout=120,env=env)
            except subprocess.TimeoutExpired:
                raise ValueError('PDF preparation timed out. Try again; first-time LaTeX setup can take longer.') from None
            if run.returncode or not (folder/'resume.pdf').exists():
                raise ValueError('LaTeX could not build the PDF. Your saved resume is unchanged.')
            if not (folder/'resume.pdf').read_bytes().startswith(b'%PDF-'):raise ValueError('The renderer did not create a PDF.')
            target.mkdir(mode=0o700)
            shutil.copy2(tex,target/'resume.tex');shutil.copy2(folder/'resume.pdf',pdf)
    return pdf,target/'resume.tex'
