import tempfile
import tkinter as tk
import threading
from pathlib import Path
from unittest.mock import patch

import github_star as gh
import quota_watcher as w
import star_ui

with tempfile.TemporaryDirectory() as directory:
    with patch.object(w, 'APP_DIR', Path(directory)), patch.object(w, 'STATE_PATH', Path(directory)/'state.json'):
        root = tk.Tk()
        root.withdraw()
        with patch.object(gh, 'client_id', return_value=''), patch.object(gh, 'star_count', return_value=7), patch.object(star_ui.webbrowser, 'open') as opened:
            panel = star_ui.show_about(root, w)
            row = next(child for child in panel.winfo_children() if isinstance(child, tk.Frame))
            star = next(child for child in row.winfo_children() if isinstance(child, tk.Button) and child.cget('text') == '⭐ Star')
            star.invoke()
            root.update()
            assert opened.call_args.args == (gh.REPO_URL,)
            assert star.cget('text') == '⭐ Star'
            assert not w.load_state().get('githubStar', {}).get('verified')
            panel.destroy()
            panel = star_ui.show_about(root, w, reminder=True)
            later = next(child for child in panel.winfo_children() if isinstance(child, tk.Button) and child.cget('text') == '以后提醒我')
            later.invoke()
            assert w.load_state()['githubStar']['next_prompt_at'] > w.load_state()['githubStar']['last_prompt_at']
        blocker = threading.Event()
        with patch.object(gh, 'client_id', return_value='id'), patch.object(gh, 'star_count', return_value=None), patch.object(gh, 'authorize_device', side_effect=lambda *args: blocker.wait(1)):
            panel = star_ui.show_about(root, w)
            row = next(child for child in panel.winfo_children() if isinstance(child, tk.Frame))
            star = next(child for child in row.winfo_children() if isinstance(child, tk.Button) and child.cget('text') == '⭐ Star')
            star.invoke()
            root.update()  # The OAuth worker is waiting, but Tk still responds.
            assert star.cget('text') == '⭐ Star'
            blocker.set()
            panel.destroy()
        w.update_github_star({'verified': True})
        with patch.object(gh, 'star_count', return_value=None):
            panel = star_ui.show_about(root, w)
            row = next(child for child in panel.winfo_children() if isinstance(child, tk.Frame))
            assert any(isinstance(child, tk.Button) and child.cget('text') == '⭐ Starred' for child in row.winfo_children())
            panel.destroy()
        root.destroy()

print('STAR_UI_OK: About button, public count, no-client fallback, responsive worker, cached verified state')
