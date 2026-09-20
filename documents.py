import hashlib
import json
from pathlib import Path
from resume_pdf import build, fingerprint, escape
from overleaf import compile_project, project_dir

def document_fingerprint(record):
 if record.get('overleaf_project'):
  return hashlib.sha256(json.dumps([record['overleaf_project'],record.get('overleaf_edits',[])],sort_keys=True).encode()).hexdigest()
 return fingerprint(record.get('draft',''))

def build_record(record,pdf_root):
 if record.get('overleaf_project'):return compile_project(Path(pdf_root).parent,record['overleaf_project'],record.get('overleaf_edits',[]))
 return build(record['draft'],pdf_root)

def source_edits(root,project_id,evidence):
 project=project_dir(root,project_id);manifest=json.loads((project/'manifest.json').read_text())
 files={n:(project/n).read_text() for n in manifest['files'] if n.endswith('.tex')}
 edits=[]
 for item in evidence:
  original=item['original'].lstrip('• ').strip();replacement=item['replacement'].lstrip('• ').strip()
  if not original or original==replacement:continue
  matches=[]
  for name,text in files.items():
   for candidate in set((original,escape(original))):
    if text.count(candidate)==1:matches.append((name,candidate))
  if len(matches)!=1:continue
  name,old=matches[0];new=escape(replacement)
  # Replace literal prose only; retain all template commands and source structure.
  if any(char in old for char in ('\\','{','}','%','\n')):continue
  edits.append(dict(file=name,original=old,replacement=new))
  files[name]=files[name].replace(old,new,1)
 return edits
