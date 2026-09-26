"""Native update action uses read-only metadata and keeps the current app open."""
import tempfile
import time
import tkinter as tk
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import app

errors=[]
original=tk.Tk.mainloop
@contextmanager
def connection(*args):yield lambda *args:{'data':[]}
def walk(widget):
    yield widget
    for child in widget.winfo_children():yield from walk(child)
def mainloop(root):
    def check():
        try:
            target=next(w for w in walk(root) if isinstance(w,tk.Button) and w.cget('text')=='检查更新')
            target.invoke()
            deadline=time.monotonic()+5
            while not opened.called and time.monotonic()<deadline:
                root.update();time.sleep(.02)
            checker.assert_called_once()
            installer.assert_not_called()
            opened.assert_called_once_with(f'https://github.com/{app.updater.REPO}/releases/tag/v3.0.0-beta.37')
            assert root.winfo_exists() and root.winfo_viewable()
            assert target.cget('text')=='检查更新'
        except BaseException as error:errors.append(error)
        finally:
            root.tray.close()
            root.destroy()
    root.after(2400,check)
    original(root)
with tempfile.TemporaryDirectory() as directory:
    response={'macosUpdate':True,'available':True,'version':'v3.0.0-beta.37','notes':'test release',
              'releaseUrl':f'https://github.com/{app.updater.REPO}/releases/tag/v3.0.0-beta.37','downloadUrl':None}
    with patch.multiple(app.w,APP_DIR=Path(directory),STATE_PATH=Path(directory)/'state.json'),patch.object(app.w.codex_status,'connection',connection),patch.object(app.w,'find_codex',return_value='mock'),patch.object(app.w,'latest_candidate',return_value=None),patch.object(app,'monitor_indicator',return_value=('test','#43c77a',True)),patch.object(app.updater,'check_macos_update',return_value=response) as checker,patch.object(app.updater,'update') as installer,patch.object(app.messagebox,'askyesno',return_value=True),patch.object(app.webbrowser,'open') as opened,patch.object(tk.Tk,'mainloop',mainloop):
        app.show()
assert not errors,errors
print('MACOS_UPDATE_UI_OK: check, release link, no install, window remains open')
