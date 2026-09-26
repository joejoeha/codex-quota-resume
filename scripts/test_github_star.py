import tempfile
from pathlib import Path
from unittest.mock import patch

import github_star as gh
import quota_watcher as w

with patch.object(gh, 'request', return_value=(200, b'{"stargazers_count": 7}')):
    assert gh.star_count() == 7
with patch.object(gh, 'request', return_value=(403, b'')):
    assert gh.star_count() is None

with patch.object(gh, 'request', side_effect=[(404, b''), (204, b'')]) as api:
    assert gh.add_star('token')
    assert [call.kwargs.get('method', 'GET') for call in api.call_args_list] == ['GET', 'PUT']
with patch.object(gh, 'request', return_value=(204, b'')) as api:
    assert gh.add_star('token') and api.call_count == 1
with patch.object(gh, 'request', return_value=(403, b'')):
    try:
        gh.add_star('token')
        assert False
    except RuntimeError:
        pass

clock = [0.0]
def sleep(seconds):
    clock[0] += seconds

with patch.object(gh, 'request', side_effect=[
    (200, b'{"device_code":"device","user_code":"ABCD","verification_uri":"https://github.com/login/device","expires_in":900,"interval":5}'),
    (200, b'{"access_token":"token"}')]), patch.object(gh.time, 'sleep', sleep), patch.object(gh.time, 'monotonic', lambda: clock[0]):
    codes = []
    assert gh.authorize_device('id', lambda *args: codes.append(args)) == 'token'
    assert codes == [('ABCD', 'https://github.com/login/device')]
with patch.object(gh, 'request', side_effect=[
    (200, b'{"device_code":"device","user_code":"ABCD","verification_uri":"https://github.com/login/device","expires_in":900,"interval":5}'),
    (200, b'{"error":"access_denied"}')]), patch.object(gh.time, 'sleep', sleep), patch.object(gh.time, 'monotonic', lambda: clock[0]):
    assert gh.authorize_device('id', lambda *args: None) is None

assert gh.reminder_due({}, 100)
deferred = gh.prompted_at(100)
assert not gh.reminder_due(deferred, 100 + gh.SEVEN_DAYS - 1)
assert gh.reminder_due(deferred, 100 + gh.SEVEN_DAYS)
assert not gh.reminder_due({'verified': True}, 100 + gh.SEVEN_DAYS)

with tempfile.TemporaryDirectory() as directory:
    with patch.object(w, 'APP_DIR', Path(directory)), patch.object(w, 'STATE_PATH', Path(directory)/'state.json'):
        w.save_state({'sent': {}})
        w.update_github_star({'verified': True, 'last_verified_at': 123})
        w.save_state({'sent': {}, 'status': 'monitor result'})
        assert w.load_state()['githubStar']['verified'] is True
        assert w.load_state()['status'] == 'monitor result'

print('GITHUB_STAR_OK: count, check/put/verify, failures, device flow, reminder, shared state')
