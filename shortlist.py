"""Local stage-one storage and conservative, explainable matching."""
import datetime as dt
import json
import re
import sqlite3
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

FIELDS = ('role', 'location', 'experience', 'skills')

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def url(value):
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Provide an original HTTP(S) listing link without embedded credentials.')
    return value

def canonical(value):
    p = urlsplit(url(value))
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('trk', 'trackingid', 'refid')]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'), urlencode(sorted(query)), ''))

def normalize(data):
    result = {key: str(data.get(key, '')).strip() for key in ('title', 'company', 'description', 'link', 'source', 'date', *FIELDS, 'evidence_link', 'evidence_notes', 'concerns', 'status')}
    if not result['description'] or not result['title']:
        raise ValueError('Title and original description/notification text are required.')
    result['link'] = url(result['link'])
    if result['evidence_link']:
        result['evidence_link'] = url(result['evidence_link'])
    if result['date']:
        dt.date.fromisoformat(result['date'])
    if result['status'] not in ('unknown', 'open', 'closed'):
        raise ValueError('Listing status must be unknown, open, or closed.')
    result['imported_at'] = now()
    result['evidence_recorded_at'] = now() if result['evidence_link'] or result['evidence_notes'] or result['concerns'] else None
    return result

def terms(value):
    return [v.strip().lower() for v in value.split(',') if v.strip()]

def contains(text, term):
    return bool(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text.lower()))

def assess(job, profile):
    reasons, gaps, excluded = [], [], []
    score, possible = 0, 0
    if job['status'] == 'closed':
        excluded.append('Listing marked closed by importer.')
    for field in FIELDS:
        # Only explicit structured facts establish a must-have; missing facts stay reviewable.
        fact = job.get(field, '') or (job['title'] if field == 'role' else '')
        for level, weight in (('must', 3), ('soft', 1)):
            for term in terms(profile.get(level + '_' + field, '')):
                possible += weight
                if not fact:
                    gaps.append(f'{field}: unknown; cannot establish {level} preference "{term}".')
                elif contains(fact, term):
                    score += weight
                    reasons.append(f'{field}: explicit text matches {level} preference "{term}".')
                elif level == 'must':
                    # Text mismatch is not proof of incompatibility, especially skills and experience.
                    gaps.append(f'{field}: must-have "{term}" not confirmed by "{fact}"; review needed.')
                else:
                    gaps.append(f'{field}: soft preference "{term}" not found.')
    for term in terms(profile.get('exclusions', '')):
        if any(contains(job.get(k, ''), term) for k in ('title', 'company', 'description', *FIELDS)):
            excluded.append(f'Explicit exclusion term found: "{term}" (check context).')
    legitimacy = 'Concerns reported' if job.get('concerns') else 'Unverified evidence supplied' if job.get('evidence_link') or job.get('evidence_notes') else 'Insufficient evidence'
    return dict(score=round(100 * score / possible) if possible else 0, reasons=reasons, gaps=gaps, excluded=excluded,
                eligibility='Excluded' if excluded else 'Needs review' if any('must-have' in x or 'must preference' in x for x in gaps) else 'Potential match',
                legitimacy=legitimacy, checked_at=now())

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, canonical TEXT UNIQUE, data TEXT, state TEXT DEFAULT "shortlisted")')
        self.db.execute('CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT)')
        self.db.commit()

    def profile(self, data=None):
        if data is not None:
            with self.db:
                self.db.execute('INSERT OR REPLACE INTO profile VALUES (1, ?)', (json.dumps(data),))
        row = self.db.execute('SELECT data FROM profile WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {}

    def add(self, data):
        job = normalize(data)
        key = canonical(job['link'])
        with self.db:
            existing = self.db.execute('SELECT id FROM jobs WHERE canonical=?', (key,)).fetchone()
            if existing:
                return existing[0], False
            cursor = self.db.execute('INSERT INTO jobs (canonical,data) VALUES (?,?)', (key, json.dumps(job)))
            return cursor.lastrowid, True

    def jobs(self):
        return [dict(json.loads(data), id=i, state=state) for i, data, state in self.db.execute('SELECT id,data,state FROM jobs')]

    def state(self, job_id, state):
        if state not in ('shortlisted', 'saved', 'dismissed', 'selected'):
            raise ValueError('Invalid state')
        if not self.db.execute('SELECT 1 FROM jobs WHERE id=?', (job_id,)).fetchone():
            raise ValueError('Unknown job')
        with self.db:
            if state == 'selected':
                self.db.execute('UPDATE jobs SET state="saved" WHERE state="selected"')
            self.db.execute('UPDATE jobs SET state=? WHERE id=?', (state, job_id))

    def handoff(self):
        return {'stage': 1, 'exported_at': now(), 'profile': self.profile(), 'selected_job': next((j for j in self.jobs() if j['state'] == 'selected'), None)}
