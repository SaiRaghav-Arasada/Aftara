"""Offline resume preparation. Never sends data or submits applications."""
import hashlib
import json
from shortlist import contains, now, terms


def prepare(source, requirements):
    source = source.strip()
    if not source or len(source) > 200000:
        raise ValueError('Paste or upload a resume between 1 and 200,000 characters.')
    requirements = terms(requirements)
    if not requirements:
        raise ValueError('Enter the job requirements to check, separated by commas.')
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    matched = [term for term in requirements if contains(source, term)]
    missing = [term for term in requirements if term not in matched]
    highlights = sorted((line for line in lines if any(contains(line, term) for term in matched)), key=lambda line: -sum(contains(line, term) for term in matched))[:6]
    # Copy complete source lines without changing dates, employers, or qualifications.
    draft = source
    return dict(source=source, requirements=', '.join(requirements), draft=draft, matched=matched, missing=missing, reviewed=False, updated_at=now())


def revision(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


class Applications:
    def __init__(self, store):
        self.store = store
        self.db = store.db
        self.db.execute('CREATE TABLE IF NOT EXISTS applications (job_id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        self.db.commit()

    def job(self, job_id):
        job = next((j for j in self.store.jobs() if j['id'] == job_id), None)
        if job is None:
            raise ValueError('Unknown job.')
        return job

    def get(self, job_id):
        row = self.db.execute('SELECT data FROM applications WHERE job_id=?', (job_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def save(self, job_id, data):
        self.job(job_id)
        current = self.get(job_id)
        if data.get('revision', '') != (revision(current) if current else ''):
            raise ValueError('This draft changed in another tab. Reload before saving.')
        action = data.get('action')
        if action == 'generate':
            record = prepare(data.get('source', ''), data.get('requirements', ''))
            record['applied_at'] = current.get('applied_at')
        elif action == 'edit':
            if not current:
                raise ValueError('Generate a draft first.')
            draft = data.get('draft', '').strip()
            if not draft or len(draft) > 250000:
                raise ValueError('Draft must contain between 1 and 250,000 characters.')
            record = dict(current, draft=draft, reviewed=data.get('reviewed') == 'yes', updated_at=now())
            record.pop('approved_pdf',None)
            record.pop('approved_at',None)
        elif action in ('applied', 'undo'):
            if not current or (action == 'applied' and data.get('confirmed') != 'yes'):
                raise ValueError('Confirm that you submitted this application on the employer’s site.')
            record = dict(current, applied_at=now() if action == 'applied' else None)
        else:
            raise ValueError('Unknown application action.')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO applications VALUES (?, ?)', (job_id, json.dumps(record)))
        return record
