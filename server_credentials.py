"""Encrypted per-account credentials for a single Linux VM.

The encryption key is provisioned outside the application data directory.
Never silently recreate it: losing it requires reconnecting saved credentials.
"""
import os
import re
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

def vault():
    try:
        key_path=Path(os.environ['LINKEDINAPPLY_VAULT_KEY'])
        if key_path.stat().st_mode & 0o077:
            raise ValueError('Server credential key permissions must be owner-only.')
        cipher=Fernet(key_path.read_bytes().strip())
        root=Path(os.environ['LINKEDINAPPLY_DATA']);root.mkdir(parents=True,exist_ok=True,mode=0o700)
        db=sqlite3.connect(root/'credentials.sqlite3',timeout=20)
        os.chmod(root/'credentials.sqlite3',0o600)
        db.execute('CREATE TABLE IF NOT EXISTS credentials (account TEXT, name TEXT, encrypted BLOB, PRIMARY KEY(account,name))')
        db.commit()
        return db,cipher
    except (OSError,KeyError,ValueError) as error:
        raise ValueError('Secure server credential storage is unavailable. Contact the administrator.') from error

def identity(uid,name):
    if not re.fullmatch('[a-f0-9]{32}',uid) or name not in ('gemini','smtp'):
        raise ValueError('Invalid credential identity.')

def read(uid,name):
    identity(uid,name);db,cipher=vault()
    try:
        row=db.execute('SELECT encrypted FROM credentials WHERE account=? AND name=?',(uid,name)).fetchone()
        if not row:return ''
        payload=cipher.decrypt(row[0]).decode()
        prefix=uid+':'+name+':'
        if not payload.startswith(prefix):raise ValueError('Saved credential does not belong to this account.')
        return payload[len(prefix):]
    except InvalidToken:
        raise ValueError('Saved credentials could not be decrypted. Contact the administrator.') from None
    finally:db.close()

def save(uid,name,value):
    identity(uid,name);db,cipher=vault()
    try:
        with db:db.execute('INSERT OR REPLACE INTO credentials VALUES (?,?,?)',(uid,name,cipher.encrypt((uid+':'+name+':'+value).encode())))
    finally:db.close()

def delete(uid,name):
    identity(uid,name);db,_=vault()
    try:
        with db:db.execute('DELETE FROM credentials WHERE account=? AND name=?',(uid,name))
    finally:db.close()
