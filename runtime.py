import threading
from browser_jobs import BrowserFinder
import credentials
_LOCK=threading.Lock();_FINDERS={}
def finder_for(uid):
    with _LOCK:
        if uid not in _FINDERS:
            finder=BrowserFinder();finder.key=credentials.read(uid,'gemini');_FINDERS[uid]=finder
        return _FINDERS[uid]
