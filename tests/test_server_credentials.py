import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
import server_credentials as vault

class VaultTests(unittest.TestCase):
 def test_encrypted_storage_isolation_and_missing_key(self):
  with tempfile.TemporaryDirectory() as d:
   key=Path(d)/'key';key.write_bytes(Fernet.generate_key());key.chmod(0o600)
   with patch.dict(os.environ,{'LINKEDINAPPLY_VAULT_KEY':str(key),'LINKEDINAPPLY_DATA':str(Path(d)/'data')}):
    one='a'*32;two='b'*32
    vault.save(one,'gemini','TEST-SECRET-ONLY')
    self.assertEqual(vault.read(one,'gemini'),'TEST-SECRET-ONLY')
    self.assertEqual(vault.read(two,'gemini'),'')
    self.assertNotIn(b'TEST-SECRET-ONLY',(Path(d)/'data'/'credentials.sqlite3').read_bytes())
    key.unlink()
    with self.assertRaises(ValueError):vault.read(one,'gemini')
