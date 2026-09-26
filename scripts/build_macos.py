"""Build on macOS only; use --dist-dir outside synced folders when needed."""
import argparse
import hashlib
import platform
import subprocess
import sys
from pathlib import Path


def main():
    if sys.platform != 'darwin':raise SystemExit('macOS .app must be built on macOS.')
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist-dir', type=Path, default=root / 'dist',
                        help='Output directory; choose a non-synced location if codesign rejects Finder metadata.')
    args = parser.parse_args()
    dist = args.dist_dir.expanduser().resolve()
    dist.mkdir(parents=True, exist_ok=True)
    build = root / 'build'
    build.mkdir(exist_ok=True)
    from PIL import Image
    with Image.open(root / 'assets/app-icon.png') as image:
        image.convert('RGBA').resize((1024, 1024)).save(build / 'app-icon.icns')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                    '--onedir', '--windowed', '--name', 'CodexQuotaResume',
                    '--osx-bundle-identifier', 'com.codexquota.desktop',
                    '--icon', str(build / 'app-icon.icns'),
                    '--add-data', str(root / 'assets/github-mark.png') + ':.',
                    '--add-data', str(root / 'assets/app-icon.png') + ':.',
                    '--hidden-import', 'AppKit', '--hidden-import', 'Foundation',
                    '--distpath', str(dist), '--workpath', str(build),
                    '--specpath', str(build), str(root / 'scripts/app.py')], check=True, cwd=root)
    bundle = dist / 'CodexQuotaResume.app'
    # Finder/framework metadata can invalidate PyInstaller's bundle signature (Apple QA1940).
    # Clean only the generated bundle's signing-incompatible attributes, preserving quarantine.
    for attribute in ('com.apple.FinderInfo', 'com.apple.ResourceFork'):
        subprocess.run(['/usr/bin/xattr', '-dr', attribute, str(bundle)], check=True)
    subprocess.run(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', str(bundle)], check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(bundle)], check=True)
    archive = dist / f'CodexQuotaResume-macOS-{platform.machine()}-preview.zip'
    subprocess.run(['/usr/bin/ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(bundle), str(archive)], check=True)
    archive.with_suffix('.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print(archive)


if __name__ == '__main__':main()
