import hashlib
import hmac
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import time

class Accounts:
    def __init__(self, root, legacy=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.legacy=Path(legacy) if legacy else None
        self.db=sqlite3.connect(self.root/'accounts.sqlite3',timeout=20)
        self.db.execute('CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY,email TEXT UNIQUE,salt TEXT,password TEXT,created REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY,user_id TEXT,expires REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS attempts (email TEXT PRIMARY KEY,count INTEGER,until_time REAL)')
        self.db.commit()
    def close(self):self.db.close()
    @staticmethod
    def digest(password,salt):return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    def register(self,email,password):
        email=email.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254:raise ValueError('Enter a valid email address.')
        if len(password)<12 or len(password)>256:raise ValueError('Use a password between 12 and 256 characters.')
        uid=secrets.token_hex(16);salt=secrets.token_hex(16)
        try:
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                first=self.db.execute('SELECT COUNT(*) FROM users').fetchone()[0]==0
                self.db.execute('INSERT INTO users VALUES (?,?,?,?,?)',(uid,email,salt,self.digest(password,salt),time.time()))
                path=self.user_db(uid)
                if first and self.legacy and self.legacy.exists():
                    # SQLite backup includes committed WAL content and leaves the original intact.
                    source=sqlite3.connect(self.legacy);dest=sqlite3.connect(path)
                    try:source.backup(dest)
                    finally:source.close();dest.close()
        except sqlite3.IntegrityError:
            raise ValueError('An account already uses this email. Sign in instead.') from None
        return uid
    def login(self,email,password):
        email=email.strip().lower()
        attempt=self.db.execute('SELECT count,until_time FROM attempts WHERE email=?',(email,)).fetchone()
        if attempt and attempt[0]>=5 and attempt[1]>time.time():raise ValueError('Too many sign-in attempts. Try again in 15 minutes.')
        row=self.db.execute('SELECT id,salt,password FROM users WHERE email=?',(email,)).fetchone()
        salt=row[1] if row else '00'*16
        valid=hmac.compare_digest(self.digest(password[:256],salt),row[2] if row else '0'*128)
        if not row or not valid:
            count=attempt[0]+1 if attempt and attempt[1]>time.time() else 1
            with self.db:self.db.execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?)',(email,count,time.time()+900))
            raise ValueError('Email or password is incorrect.')
        with self.db:self.db.execute('DELETE FROM attempts WHERE email=?',(email,))
        return row[0]
    def create_session(self,uid):
        token=secrets.token_urlsafe(32)
        with self.db:
            self.db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            self.db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,time.time()+7*86400))
        return token
    def session(self,token):
        row=self.db.execute('SELECT u.id,u.email FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        return {'id':row[0],'email':row[1],'csrf':hashlib.sha256((token+'csrf').encode()).hexdigest()} if row else None
    def logout(self,token):
        with self.db:self.db.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
    def user_db(self,uid):
        if not re.fullmatch('[a-f0-9]{32}',uid):raise ValueError('Invalid account.')
        path=self.root/'users'/uid;path.mkdir(parents=True,exist_ok=True,mode=0o700)
        return path/'shortlist.sqlite3'
    def users(self):return self.db.execute('SELECT id,email FROM users').fetchall()
