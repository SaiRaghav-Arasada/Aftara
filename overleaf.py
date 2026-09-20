"""Immutable Overleaf source imports and isolated, template-preserving compilation."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

MAX_BYTES=20_000_000
MAX_TOTAL=60_000_000
EXTENSIONS={'.tex','.cls','.sty','.bib','.bst','.png','.jpg','.jpeg','.pdf','.eps','.otf','.ttf','.txt','.md','.cfg','.def','.clo','.fd','.bbx','.cbx','.lbx','.ist'}

def safe_path(name):
 p=PurePosixPath(name)
 if not name or '\\' in name or p.is_absolute() or '..' in p.parts or any(x.startswith('.') and x!='.' for x in p.parts):
  raise ValueError('The archive contains an unsafe path.')
 if p.suffix.lower() not in EXTENSIONS:return None
 return str(p)

def unpack(payload,filename):
 if len(payload)>MAX_BYTES:raise ValueError('Upload a project smaller than 20 MB.')
 files={};total=0
 def add(name,size,reader):
  nonlocal total
  safe=safe_path(name)
  if safe is None:return
  if len(files)>=500 or size>MAX_BYTES or total+size>MAX_TOTAL:raise ValueError('The expanded project is too large.')
  value=reader(MAX_BYTES+1)
  if len(value)!=size:raise ValueError('The archive contains an invalid file size.')
  if safe in files:raise ValueError('The archive contains duplicate file names.')
  files[safe]=value;total+=size
 try:
  if filename.lower().endswith('.tex'):add('main.tex',len(payload),io.BytesIO(payload).read)
  elif zipfile.is_zipfile(io.BytesIO(payload)):
   with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    for info in archive.infolist():
     if info.is_dir():continue
     if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Links are not allowed in source archives.')
     with archive.open(info) as stream:add(info.filename,info.file_size,stream.read)
  else:
   with tarfile.open(fileobj=io.BytesIO(payload),mode='r:*') as archive:
    for info in archive:
     if info.isdir():continue
     if not info.isfile():raise ValueError('Only ordinary files are allowed in source archives.')
     with archive.extractfile(info) as stream:add(info.name,info.size,stream.read)
 except (tarfile.TarError,zipfile.BadZipFile,RuntimeError,EOFError,OSError):
  raise ValueError('Upload a valid .tex, .zip, .tar or .tar.gz project.') from None
 if not any(n.endswith('.tex') for n in files):raise ValueError('No TeX source was found.')
 return files

def save_project(root,files,main=''):
 candidates=[n for n,b in files.items() if n.endswith('.tex') and re.search(rb'\\documentclass\b',b)]
 if main:
  if main not in files or not main.endswith('.tex'):raise ValueError('The main TeX file is not in this archive.')
 elif len(candidates)==1:main=candidates[0]
 elif 'main.tex' in candidates:main='main.tex'
 else:raise ValueError('Specify the main TeX file, for example resume.tex. Candidates: '+', '.join(candidates[:8]))
 digest=hashlib.sha256(main.encode()+b'\0'+b''.join(n.encode()+b'\0'+files[n] for n in sorted(files))).hexdigest()
 root=Path(root)/'overleaf';root.mkdir(exist_ok=True,parents=True,mode=0o700)
 target=root/digest
 if not target.exists():
  with tempfile.TemporaryDirectory(dir=root) as d:
   stage=Path(d)/'project';stage.mkdir()
   for name,value in files.items():
    p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value)
   (stage/'manifest.json').write_text(json.dumps({'main':main,'files':list(files)}))
   stage.rename(target)
 return digest

def project_dir(root,project_id):
 if not re.fullmatch('[a-f0-9]{64}',project_id):raise ValueError('Invalid resume project.')
 path=Path(root)/'overleaf'/project_id
 if not (path/'manifest.json').exists():raise ValueError('Resume project not found.')
 return path

def compile_project(root,project_id,edits=None):
 project=project_dir(root,project_id);manifest=json.loads((project/'manifest.json').read_text());edits=edits or []
 revision=hashlib.sha256(json.dumps([project_id,edits],sort_keys=True).encode()).hexdigest()
 output=Path(root)/'pdfs'/('overleaf-'+revision)
 if (output/'resume.pdf').exists():return output/'resume.pdf',output/'source.zip'
 # Never compile uploaded TeX with access to account databases, credentials or host home directories.
 bwrap=shutil.which('bwrap')
 if not bwrap:raise ValueError('Original-template rendering needs the server’s isolated LaTeX compiler. Your project is saved; the administrator must install bubblewrap.')
 binary=Path(__file__).with_name('bin')/'tectonic'
 cache=Path(__file__).with_name('latex-cache');cache.mkdir(exist_ok=True)
 output.parent.mkdir(exist_ok=True,parents=True)
 with tempfile.TemporaryDirectory(dir=output.parent) as d:
  work=Path(d);source=work/'source';shutil.copytree(project,source)
  for edit in edits:
   name=edit['file']
   if name not in manifest['files'] or not name.endswith('.tex'):raise ValueError('Invalid edited source file.')
   p=source/name;text=p.read_text()
   if text.count(edit['original'])!=1:raise ValueError('The original wording could not be identified uniquely.')
   p.write_text(text.replace(edit['original'],edit['replacement'],1))
  compiled=work/'compiled';compiled.mkdir()
  command=[bwrap,'--die-with-parent','--unshare-all','--share-net','--new-session','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
  for path in ('/usr','/bin','/lib','/lib64'):
   if Path(path).exists():command+=['--ro-bind',path,path]
  command+=['--dir','/etc']
  for path in ('/etc/ssl','/etc/fonts','/etc/resolv.conf','/etc/hosts'):
   if Path(path).exists():command+=['--ro-bind',path,path]
  biber_dir=Path(__file__).with_name('bin')/'biber-2.17'
  if (biber_dir/'biber').exists():command+=['--ro-bind',str(biber_dir.resolve()),'/compiler-bin']
  command+=['--ro-bind',str(binary.resolve()),'/tectonic','--bind',str(cache.resolve()),'/cache','--bind',str(source.resolve()),'/work','--bind',str(compiled.resolve()),'/output','--chdir','/work','--clearenv','--setenv','PATH','/compiler-bin:/usr/bin:/bin','--setenv','HOME','/tmp','--setenv','TECTONIC_CACHE_DIR','/cache','/tectonic','--untrusted','--outdir','/output',manifest['main']]
  try:result=subprocess.run(['/usr/bin/prlimit','--as=1610612736','--fsize=25000000','--cpu=90','--nofile=256','--']+command,capture_output=True,timeout=120)
  except subprocess.TimeoutExpired:raise ValueError('Original-template compilation timed out. Retry once after resources finish downloading.') from None
  pdf=compiled/(Path(manifest['main']).stem+'.pdf')
  if result.returncode or not pdf.exists():
   detail=re.search(r'^error: ([^\n]{1,350})',result.stderr.decode(errors='replace'),re.MULTILINE)
   reason=detail.group(1) if detail else 'Check the main TeX file and include its fonts, class files and images.'
   raise ValueError('Your Overleaf project could not compile: '+reason+' Your source is saved unchanged; no replacement PDF was generated.')
  shutil.copy2(pdf,work/'resume.pdf')
  with zipfile.ZipFile(work/'source.zip','w',zipfile.ZIP_DEFLATED) as archive:
   for name in manifest['files']:archive.write(source/name,name)
  output.mkdir(exist_ok=True)
  shutil.copy2(work/'resume.pdf',output/'resume.pdf');shutil.copy2(work/'source.zip',output/'source.zip')
 return output/'resume.pdf',output/'source.zip'

def pdf_text(pdf):
 try:
  result=subprocess.run(['pdftotext','-layout',str(pdf),'-'],capture_output=True,timeout=20,check=True)
 except (OSError,subprocess.SubprocessError):raise ValueError('PDF text extraction is unavailable on the server.') from None
 return result.stdout.decode(errors='replace').strip()
