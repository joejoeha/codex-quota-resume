"""The footer only reads a public count and opens the repository."""
import io
from unittest.mock import patch
import urllib.error

import github_star as gh

with patch.object(gh.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"stargazers_count":7}')):
    assert gh.star_count() == 7
with patch.object(gh.urllib.request, 'urlopen', side_effect=urllib.error.HTTPError('', 403, '', {}, None)):
    assert gh.star_count() is None

assert gh.REPO_URL == 'https://github.com/joejoeha/codex-quota-resume'
print('GITHUB_STAR_OK: public count and repository link')
