"""Smoke a running fixture API without provider credentials.

Usage: python scripts/demo_smoke.py --base http://localhost:8000/api/v1
Creates an interview and finishes early; use demo reset between rehearsals.
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://localhost:8000/api/v1')
    parser.add_argument('--token', default='demo-learner-token')
    args = parser.parse_args()

    def request(path, body=None):
        headers = {'Authorization': f'Bearer {args.token}', 'Content-Type': 'application/json'}
        if body is not None:
            headers['Idempotency-Key'] = str(uuid4())
        req = urllib.request.Request(args.base.rstrip('/') + path,
                                     data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise SystemExit(f'{req.method} {path}: HTTP {error.code}: {error.read().decode()}')

    bootstrap = request('/demo/bootstrap')
    attempts = bootstrap['attempts']
    if not attempts:
        raise SystemExit('No completed attempts available for this learner.')
    session = request('/viva/sessions', {'attempt_id': attempts[0]['id'], 'input_mode': 'text'})
    session_id = session['id']
    job = request(f'/viva/sessions/{session_id}/finish', {'expected_revision': session['revision']})
    for _ in range(30):
        job = request(f'/viva/sessions/{session_id}/evaluation')
        if job['status'] in ('completed', 'failed'):
            break
        time.sleep(1)
    if job['status'] != 'completed':
        raise SystemExit(f'Evaluation did not complete: {job}')
    report = request(f'/viva/sessions/{session_id}/result')
    assert report['release_id'] == session['release_id']
    assert report['source_index'], 'Missing complete source index'
    print(json.dumps({'session_id': session_id, 'report_id': report['id'],
                      'completion': report['completion'], 'sources': len(report['source_index'])}, indent=2))


if __name__ == '__main__':
    main()
