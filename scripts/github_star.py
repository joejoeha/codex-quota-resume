"""Optional GitHub Star integration. No GitHub credential is stored on disk."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_URL = 'https://github.com/joejoeha/codex-quota-resume'
API_URL = 'https://api.github.com'
STAR_PATH = '/user/starred/joejoeha/codex-quota-resume'
HEADERS = {'Accept': 'application/vnd.github+json',
           'User-Agent': 'Codex-Quota-Resume',
           'X-GitHub-Api-Version': '2026-03-10'}
SEVEN_DAYS = 7 * 24 * 60 * 60


def client_id():
    embedded = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'github-client-id.txt'
    if embedded.exists():
        return embedded.read_text(encoding='utf-8-sig').strip()
    return os.environ.get('CODEX_QUOTA_GITHUB_CLIENT_ID', '').strip()


def request(url, *, method='GET', token=None, form=None):
    headers = dict(HEADERS)
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if form is not None:
        data = urllib.parse.urlencode(form).encode('ascii')
        headers['Accept'] = 'application/json'
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif method == 'PUT':
        data = b''
        headers['Content-Length'] = '0'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def star_count(token=None):
    status, body = request(API_URL + '/repos/joejoeha/codex-quota-resume', token=token)
    if status != 200:
        return None
    value = json.loads(body).get('stargazers_count')
    return value if type(value) is int and value >= 0 else None


def is_starred(token):
    status, _ = request(API_URL + STAR_PATH, token=token)
    if status == 204:
        return True
    if status == 404:
        return False
    raise RuntimeError('GitHub Star status unavailable')


def add_star(token):
    if is_starred(token):
        return True
    status, _ = request(API_URL + STAR_PATH, method='PUT', token=token)
    if status != 204:
        raise RuntimeError('GitHub could not add Star')
    return True


def authorize_device(client, show_code, cancelled=lambda: False):
    """GitHub App device flow: public-client safe, no client secret or token persistence."""
    status, body = request('https://github.com/login/device/code', method='POST',
                           form={'client_id': client})
    if status != 200:
        raise RuntimeError('GitHub authorization unavailable')
    data = json.loads(body)
    code = data['device_code']
    show_code(data['user_code'], data['verification_uri'])
    interval = max(5, int(data.get('interval', 5)))
    expires = time.monotonic() + min(900, int(data.get('expires_in', 900)))
    while time.monotonic() < expires and not cancelled():
        until = time.monotonic() + interval
        while time.monotonic() < until:
            if cancelled():
                return None
            time.sleep(max(0, min(0.25, until - time.monotonic())))
        status, body = request('https://github.com/login/oauth/access_token', method='POST',
                               form={'client_id': client, 'device_code': code,
                                     'grant_type': 'urn:ietf:params:oauth:grant-type:device_code'})
        if status != 200:
            raise RuntimeError('GitHub authorization unavailable')
        response = json.loads(body)
        if response.get('access_token'):
            return response['access_token']
        error = response.get('error')
        if error == 'slow_down':
            interval = max(interval + 5, int(response.get('interval', interval + 5)))
        elif error != 'authorization_pending':
            return None
    return None


def reminder_due(star, now):
    return not star.get('verified') and now >= star.get('next_prompt_at', 0)


def prompted_at(now):
    return {'last_prompt_at': now, 'next_prompt_at': now + SEVEN_DAYS}
