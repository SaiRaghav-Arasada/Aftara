from pathlib import Path
import os
from cryptography.fernet import Fernet
root=Path.home()/'linkedinapply'
secrets=Path.home()/'.config'/'linkedinapply';secrets.mkdir(parents=True,exist_ok=True,mode=0o700)
key=secrets/'vault.key'
if not key.exists():
 fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as output:output.write(Fernet.generate_key())
(root/'data').mkdir(mode=0o700,exist_ok=True)
(root/'latex-cache').mkdir(exist_ok=True)
(root/'service.env').write_text(f'''LINKEDINAPPLY_DATA={root}/data
LINKEDINAPPLY_VAULT_KEY={key}
LINKEDINAPPLY_CHROMIUM=/usr/bin/chromium
LINKEDINAPPLY_REMOTE_BROWSER=yes
LINKEDINAPPLY_PUBLIC_ORIGIN=http://127.0.0.1:8505
LINKEDINAPPLY_MAX_BROWSERS=2
''')
(root/'service.env').chmod(0o600)
unit=Path.home()/'.config/systemd/user';unit.mkdir(parents=True,exist_ok=True)
(unit/'linkedinapply.service').write_text(f'''[Unit]
Description=LinkedInApply application and private browser gateway
After=network-online.target
[Service]
WorkingDirectory={root}
EnvironmentFile={root}/service.env
ExecStart={root}/.venv/bin/python -B {root}/gateway.py
Restart=on-failure
RestartSec=5
UMask=0077
[Install]
WantedBy=default.target
''')
print('Application configuration created; no credentials printed.')
