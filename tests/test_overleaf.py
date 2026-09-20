import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from overleaf import unpack,save_project,project_dir
from documents import document_fingerprint,source_edits

class OverleafTests(unittest.TestCase):
 def test_zip_preserves_source_and_assets(self):
  content=b'\\documentclass{article}\n\\begin{document}Built Python tools.\\end{document}'
  archive=io.BytesIO()
  with zipfile.ZipFile(archive,'w') as z:z.writestr('resume.tex',content);z.writestr('custom.cls',b'CUSTOM CLASS')
  files=unpack(archive.getvalue(),'project.zip')
  with tempfile.TemporaryDirectory() as root:
   pid=save_project(root,files)
   self.assertEqual((project_dir(root,pid)/'resume.tex').read_bytes(),content)
   edits=source_edits(root,pid,[dict(original='• Built Python tools.',replacement='• Created Python tools.')])
   self.assertEqual(len(edits),1)
   self.assertEqual((project_dir(root,pid)/'resume.tex').read_bytes(),content)
   self.assertNotEqual(document_fingerprint({'overleaf_project':pid}),document_fingerprint({'overleaf_project':pid,'overleaf_edits':edits}))
 def test_tar_and_unsafe_archives(self):
  data=b'\\documentclass{article}'
  archive=io.BytesIO()
  with tarfile.open(fileobj=archive,mode='w:gz') as t:
   info=tarfile.TarInfo('main.tex');info.size=len(data);t.addfile(info,io.BytesIO(data))
  self.assertEqual(unpack(archive.getvalue(),'project.tar.gz')['main.tex'],data)
  archive=io.BytesIO()
  with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.tex',data)
  with self.assertRaises(ValueError):unpack(archive.getvalue(),'project.zip')
  archive=io.BytesIO()
  with tarfile.open(fileobj=archive,mode='w') as t:
   info=tarfile.TarInfo('link.tex');info.type=tarfile.SYMTYPE;info.linkname='/etc/passwd';t.addfile(info)
  with self.assertRaises(ValueError):unpack(archive.getvalue(),'project.tar')
