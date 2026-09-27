"""GitHub release updates; keep running binaries and user data intact."""
import base64
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
import urllib.parse
from xml.etree import ElementTree as ET

VERSION = '3.0.0-beta.44'
REPO = 'joejoeha/codex-quota-resume'
ASSET = 'CodexQuotaResume.exe'


def version(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?', value)
    if not match:
        return None
    major, minor, patch, beta = match.groups()
    return int(major), int(minor), int(patch), beta is None, int(beta or 0)


def fetch(url, method='GET'):
    return urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': 'CodexQuotaResume/' + VERSION}, method=method), timeout=60)


def asset_url(release, name):
    expected = f'https://github.com/{REPO}/releases/download/{release["tag_name"]}/{name}'
    asset = next((a for a in release['assets'] if a['name'] == name), None)
    if not asset or asset.get('browser_download_url') != expected:
        raise RuntimeError('GitHub 发布附件缺失或下载地址不匹配。')
    return expected


def check_macos_update(current=VERSION, machine=None):
    """Read release metadata only; macOS installation stays an explicit download."""
    if not version(current):raise ValueError('当前版本号无效。')
    architecture=machine or platform.machine()
    asset=f'CodexQuotaResume-macOS-{architecture}-preview.zip'
    fallback=False
    try:
        with fetch(f'https://api.github.com/repos/{REPO}/releases?per_page=100') as response:
            releases=json.load(response)
    except urllib.error.HTTPError as error:
        if error.code not in (403,429):raise
        with fetch(f'https://github.com/{REPO}/releases/latest?check={int(time.time())}') as response:
            url=response.geturl()
        prefix=f'https://github.com/{REPO}/releases/tag/'
        tag=urllib.parse.unquote(url[len(prefix):]) if url.startswith(prefix) else ''
        if not version(tag):raise RuntimeError('无法确认 GitHub 最新版本，请稍后重试。')
        releases=[{'tag_name':tag,'assets':[]}]
        fallback=True
    candidates=[r for r in releases if not r.get('draft') and version(r.get('tag_name',''))
                and version(r['tag_name'])>version(current)]
    if not candidates:
        return {'macosUpdate':True,'available':False,'version':current,'limited':fallback}
    release=max(candidates,key=lambda r:version(r['tag_name']))
    tag=release['tag_name']
    download=None
    if any(a.get('name')==asset for a in release.get('assets',[])):
        download=asset_url(release,asset)
    return {'macosUpdate':True,'available':True,'version':tag,'limited':fallback,
            'releaseUrl':f'https://github.com/{REPO}/releases/tag/{tag}',
            'downloadUrl':download,'notes':release.get('body') or ''}


def activate(executable, run_command):
    """Change only task actions; retain triggers, enabled state and running jobs."""
    target = str(Path(executable).resolve()).replace("'", "''")
    script = r"""
$ErrorActionPreference='Stop'
$target='TARGET'
$previous=@()
try {
  $names=@('Codex Quota Resume Watcher','Codex Quota Resume Backup')
  $arguments=@('--monitor','--monitor --backup')
  for($i=0;$i -lt 2;$i++) {
    $task=Get-ScheduledTask -TaskName $names[$i] -ErrorAction SilentlyContinue
    if($task) {
      $previous+=@{Name=$names[$i];Actions=$task.Actions}
      $action=New-ScheduledTaskAction -Execute $target -Argument $arguments[$i] -WorkingDirectory (Split-Path $target)
      Set-ScheduledTask -TaskName $names[$i] -Action $action | Out-Null
    }
  }
  $path=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex Quota Resume.lnk'
  $shortcut=(New-Object -ComObject WScript.Shell).CreateShortcut($path)
  $shortcut.TargetPath=$target
  $shortcut.Arguments=''
  $shortcut.WorkingDirectory=Split-Path $target
  $shortcut.IconLocation=$target+',0'
  $shortcut.Save()
} catch {
  foreach($old in $previous) { Set-ScheduledTask -TaskName $old.Name -Action $old.Actions | Out-Null }
  throw
}
""".replace('TARGET', target)
    run_command(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                 base64.b64encode(script.encode('utf-16le')).decode('ascii')])


def windows_release(current=VERSION):
    try:
        with fetch(f'https://api.github.com/repos/{REPO}/releases?per_page=100') as response:
            releases = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code not in (403, 429):raise
        with fetch(f'https://github.com/{REPO}/releases.atom') as response:
            feed = ET.fromstring(response.read())
        prefix = f'https://github.com/{REPO}/releases/tag/'
        releases = []
        for entry in feed.findall('{http://www.w3.org/2005/Atom}entry'):
            link = entry.find('{http://www.w3.org/2005/Atom}link')
            url = link.get('href', '') if link is not None else ''
            tag = urllib.parse.unquote(url[len(prefix):]) if url.startswith(prefix) else ''
            if not version(tag) or version(tag) <= version(current):continue
            assets = []
            for name in (ASSET, 'SHA256SUMS.txt'):
                asset = f'https://github.com/{REPO}/releases/download/{tag}/{name}'
                try:
                    with fetch(asset, method='HEAD'):pass
                except urllib.error.HTTPError as missing:
                    if missing.code == 404:break
                    raise
                assets.append({'name': name, 'browser_download_url': asset})
            if len(assets) == 2:releases.append({'draft': False, 'tag_name': tag, 'assets': assets})
    candidates = [r for r in releases if not r['draft'] and version(r['tag_name'])
                  and version(r['tag_name']) > version(current)
                  and {ASSET, 'SHA256SUMS.txt'} <= {a['name'] for a in r['assets']}]
    return max(candidates, key=lambda r: version(r['tag_name'])) if candidates else None


def check_windows_update(current=VERSION):
    """Check release metadata without downloading or installing anything."""
    return windows_release(current) is not None


def prune_versions(directory, executable):
    """Remove superseded installed versions; retry locked files on next launch."""
    versions = Path(directory).resolve() / 'versions'
    executable = Path(executable).resolve()
    if executable.name != ASSET or executable.parent.parent != versions:
        return
    current = version(executable.parent.name)
    if current is None:
        return
    for folder in versions.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            continue
        older = version(folder.name)
        if older is not None and older < current:
            try:
                shutil.rmtree(folder)
            except OSError:
                pass  # A running old EXE is locked on Windows; try again next launch.


def update(directory, progress=lambda text: None, current=VERSION):
    if os.name != 'nt':
        raise RuntimeError('macOS 开发预览暂不支持自动安装，请从 GitHub Releases 下载。')
    import msvcrt
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'update.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('另一个窗口正在更新，请稍后重试。')
        progress('正在检查 GitHub 新版本…')
        release = windows_release(current)
        if not release:
            return {'updated': False, 'version': current}
        tag = release['tag_name']
        with fetch(asset_url(release, 'SHA256SUMS.txt')) as response:
            sums = response.read().decode('utf-8-sig')
        matches = re.findall(r'^([a-fA-F0-9]{64})\s+\*?' + re.escape(ASSET) + r'\s*$', sums, re.M)
        if len(matches) != 1:
            raise RuntimeError('发布版本缺少有效 SHA256 校验值。')
        expected = matches[0].lower()
        destination = directory / 'versions' / tag / ASSET
        destination.parent.mkdir(parents=True, exist_ok=True)
        progress('正在下载 ' + tag + '…')
        with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.download', delete=False) as output:
            temporary = Path(output.name)
            try:
                digest = hashlib.sha256()
                with fetch(asset_url(release, ASSET)) as response:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                        digest.update(chunk)
            except BaseException:
                output.close()
                temporary.unlink(missing_ok=True)
                raise
        try:
            if digest.hexdigest() != expected:
                raise RuntimeError('下载校验失败，未安装；请重新点击更新。')
            if destination.exists():
                if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
                    raise RuntimeError('本地同版本文件不一致，未覆盖正在使用的程序。')
            else:
                temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        progress('校验通过，正在安装 ' + tag + '…')
        environment = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')
        result = subprocess.run([str(destination), '--apply-update'], env=environment,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=180)
        if result.returncode:
            raise RuntimeError('安装切换失败，旧窗口已保留，请查看运行记录。')
        subprocess.Popen([str(destination)], env=environment)
        return {'updated': True, 'version': tag}
