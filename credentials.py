"""Account-scoped macOS Keychain storage. No plaintext fallback."""
import subprocess
import sys
import os

def read(uid,name):
    if sys.platform!='darwin':
        from server_credentials import read as server_read
        return server_read(uid,name)
    try:
        result=subprocess.run(['security','find-generic-password','-s','LinkedInApply','-a',uid+':'+name,'-w'],capture_output=True,text=True,timeout=15)
        return result.stdout.strip() if result.returncode==0 else ''
    except (OSError,subprocess.TimeoutExpired):return ''

def save(uid,name,value):
    if sys.platform!='darwin':
        from server_credentials import save as server_save
        return server_save(uid,name,value)
    try:
        result=subprocess.run(['security','add-generic-password','-U','-s','LinkedInApply','-a',uid+':'+name,'-w',value],capture_output=True,timeout=20)
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError('Keychain is unavailable. Unlock it and try again.') from None
    if result.returncode:raise ValueError('Keychain could not save the credential. Unlock your login keychain and try again.')

def delete(uid,name):
    if sys.platform!='darwin':
        from server_credentials import delete as server_delete
        return server_delete(uid,name)
    if sys.platform=='darwin':subprocess.run(['security','delete-generic-password','-s','LinkedInApply','-a',uid+':'+name],capture_output=True,timeout=15)
