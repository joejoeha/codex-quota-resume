"""Update selection, checksum rejection, install and pause-preserving activation."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import updater as u

assert u.version('v3.0.0-beta.16') > u.version('v3.0.0-beta.15')
assert u.version('3.0.0') > u.version('3.0.0-beta.99')
assert u.version('../outside') is None
payload=b'test executable'
release={'draft':False,'tag_name':'v3.0.0-beta.16','assets':[
    {'name':name,'browser_download_url':f'https://github.com/{u.REPO}/releases/download/v3.0.0-beta.16/{name}'}
    for name in (u.ASSET,'SHA256SUMS.txt')]}
def fetch(url):
    if '/api.' in url:return io.BytesIO(json.dumps([release]).encode())
    if url.endswith('SHA256SUMS.txt'):return io.BytesIO((hashlib.sha256(payload).hexdigest()+'  '+u.ASSET).encode())
    return io.BytesIO(payload)
with tempfile.TemporaryDirectory() as folder, patch.object(u,'fetch',side_effect=fetch), patch.object(u.subprocess,'run') as run, patch.object(u.subprocess,'Popen') as launch:
    run.return_value.returncode=0
    root=Path(folder);(root/'paused.flag').touch();(root/'plan.json').write_text('draft')
    assert u.check_windows_update(current='3.0.0-beta.15')
    assert not u.check_windows_update(current='3.0.0-beta.16')
    assert not run.called and not launch.called
    assert not u.update(root,current='3.0.0-beta.16')['updated']
    assert not run.called
    assert u.update(root,current='3.0.0-beta.15')['updated']
    assert run.call_args.args[0][-1]=='--apply-update' and launch.called
    assert (root/'paused.flag').exists() and (root/'plan.json').read_text()=='draft'
    run.reset_mock();launch.reset_mock()
    good=fetch
    def corrupt(url):return io.BytesIO(b'corrupt') if url.endswith('.exe') else good(url)
    with patch.object(u,'fetch',side_effect=corrupt):
        try:u.update(root,current='3.0.0-beta.15')
        except RuntimeError as e:assert '校验失败' in str(e)
        else:raise AssertionError('Corrupted download accepted')
    assert not run.called and not launch.called
    assert not list(root.rglob('*.download'))
commands=[]
u.activate('example.exe',commands.append)
script=base64.b64decode(commands[0][-1]).decode('utf-16le')
assert 'Set-ScheduledTask' in script
assert all(x not in script for x in ('Stop-ScheduledTask','Enable-ScheduledTask','Start-ScheduledTask','paused.flag'))
with tempfile.TemporaryDirectory() as folder:
    atom=f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><link href="https://github.com/{u.REPO}/releases/tag/v3.0.0-beta.16"/></entry></feed>'.encode()
    def limited(url,method='GET'):
        if 'api.github.com' in url:raise u.urllib.error.HTTPError(url,403,'rate limit',{},None)
        if url.endswith('releases.atom'):return io.BytesIO(atom)
        if method=='HEAD':return io.BytesIO()
        raise AssertionError(url)
    with patch.object(u,'fetch',side_effect=limited):
        assert u.check_windows_update(current='3.0.0-beta.15')
        assert not u.check_windows_update(current='3.0.0-beta.16')
        assert not u.update(folder)['updated']
    def missing(url,method='GET'):
        if method=='HEAD':raise u.urllib.error.HTTPError(url,404,'missing',{},None)
        return limited(url,method)
    with patch.object(u,'fetch',side_effect=missing):
        assert not u.check_windows_update(current='3.0.0-beta.15')
print('UPDATER_OK')
