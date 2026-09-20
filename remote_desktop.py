"""One private X display per active account; VNC listens only on loopback."""
import atexit
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path
_LOCK=threading.Lock()
_DESKTOPS={}

def stop_all():
    for value in _DESKTOPS.values():
        for process in reversed(value['processes']):
            process.terminate()
atexit.register(stop_all)

def get(uid):
    with _LOCK:
        value=_DESKTOPS.get(uid)
        return value if value and all(p.poll() is None for p in value['processes']) else None

def start(uid):
    if not re.fullmatch('[a-f0-9]{32}',uid):raise ValueError('Invalid browser account.')
    with _LOCK:
        old=_DESKTOPS.get(uid)
        if old and all(p.poll() is None for p in old['processes']):return old
        if old:
            for process in old['processes']:
                if process.poll() is None:process.terminate()
            del _DESKTOPS[uid]
        if len(_DESKTOPS)>=int(os.environ.get('LINKEDINAPPLY_MAX_BROWSERS','2')):
            raise ValueError('The server’s browser capacity is in use. Try again later.')
        display=next((n for n in range(100,200) if not Path(f'/tmp/.X{n}-lock').exists()),None)
        if display is None:raise ValueError('No browser display is available.')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        processes=[]
        try:
            processes.append(subprocess.Popen(['Xvfb',f':{display}','-screen','0','1280x850x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            for _ in range(50):
                if Path(f'/tmp/.X11-unix/X{display}').exists():break
                if processes[0].poll() is not None:raise ValueError('Could not start the browser display.')
                time.sleep(.1)
            processes.append(subprocess.Popen(['x11vnc','-display',f':{display}','-localhost','-rfbport',str(port),'-forever','-shared','-nopw','-quiet'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
            for _ in range(50):
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.1):break
                except OSError:time.sleep(.1)
            else:raise ValueError('Could not start the browser connection.')
            value={'display':f':{display}','port':port,'processes':processes};_DESKTOPS[uid]=value
            return value
        except Exception:
            for process in reversed(processes):process.terminate()
            raise

def stop(uid):
    with _LOCK:
        value=_DESKTOPS.pop(uid,None)
        if value:
            for process in reversed(value['processes']):process.terminate()
