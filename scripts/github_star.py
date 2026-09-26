"""Public GitHub Star count and repository link; no account access."""
import json
import urllib.error
import urllib.request

REPO_URL = 'https://github.com/joejoeha/codex-quota-resume'


def star_count():
    request = urllib.request.Request(
        'https://api.github.com/repos/joejoeha/codex-quota-resume',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'Codex-Quota-Resume'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            value = json.load(response).get('stargazers_count')
    except urllib.error.HTTPError:
        return None
    return value if type(value) is int and value >= 0 else None
