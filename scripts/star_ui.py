"""Small Tk About panel for the optional GitHub Star action."""
import queue
import threading
import time
import tkinter as tk
import webbrowser

import github_star as gh
from window_ui import FONT_FAMILY, RoundedButton


def show_about(parent, watcher, reminder=False):
    panel = tk.Toplevel(parent)
    panel.title('关于 Codex Quota Resume')
    panel.configure(bg='#181818')
    panel.resizable(False, False)
    panel.transient(parent)
    panel.geometry(f'390x240+{parent.winfo_rootx()+20}+{parent.winfo_rooty()+60}')
    items = queue.Queue()
    cancel = threading.Event()
    star = watcher.load_state().get('githubStar', {})
    verified = [bool(star.get('verified'))]
    working = [False]

    def label(value, size=10, color='#eeeeee'):
        widget = tk.Label(panel, text=value, bg='#181818', fg=color,
                          font=(FONT_FAMILY, size), anchor='w', justify='left', wraplength=350)
        widget.pack(fill='x', padx=20, pady=(10, 0))
        return widget

    label('Codex Quota Resume', 16)
    label('如果这个工具帮助到了你，欢迎在 GitHub 给项目点个 Star ⭐')
    status = label('已由 GitHub 确认 Star' if verified[0] else '', 9, '#aaaaaa')
    row = tk.Frame(panel, bg='#181818')
    row.pack(fill='x', padx=20, pady=(14, 0))

    def button(text, command, blue=False):
        widget = RoundedButton(row, text=text, command=command,
                               bg='#2d6acb' if blue else '#2b2b2b',
                               font=(FONT_FAMILY, 10), padx=11, pady=7)
        widget.pack(side='left', padx=(0, 8))
        return widget

    button('GitHub', lambda: webbrowser.open(gh.REPO_URL))

    def fallback():
        status.configure(text='请在 GitHub 页面点击 Star。')
        webbrowser.open(gh.REPO_URL)

    def start_star(force=False):
        if verified[0] and not force:
            webbrowser.open(gh.REPO_URL)
            return
        if working[0]:
            return
        client = gh.client_id()
        if not client:
            fallback()
            return
        working[0] = True
        status.configure(text='正在连接 GitHub…')

        def work():
            try:
                token = gh.authorize_device(client,
                    lambda code, url: items.put(('code', (code, url))), cancel.is_set)
                if cancel.is_set():
                    return
                if token and gh.add_star(token):
                    watcher.update_github_star({'verified': True, 'last_verified_at': time.time()})
                    items.put(('verified', None))
                    try:
                        items.put(('count', gh.star_count(token)))
                    except Exception:
                        pass
                else:
                    items.put(('fallback', None))
            except Exception:
                items.put(('fallback', None))

        threading.Thread(target=work, daemon=True).start()

    star_button = button('⭐ Starred' if verified[0] else '⭐ Star', lambda: start_star(), True)
    if verified[0]:
        star_button.configure(bg='#21854d')
    count = tk.Label(row, text='⭐ …', bg='#181818', fg='#aaaaaa', font=(FONT_FAMILY, 10))
    count.pack(side='left')

    def later():
        watcher.update_github_star(gh.prompted_at(time.time()))
        panel.destroy()

    if reminder and not verified[0]:
        later_button = RoundedButton(panel, text='以后提醒我', command=later,
                                     font=(FONT_FAMILY, 9), padx=10, pady=6)
        later_button.pack(anchor='w', padx=20, pady=(12, 0))
    elif verified[0]:
        tk.Button(panel, text='重新验证', command=lambda: start_star(True),
                  bg='#181818', fg='#aaaaaa', bd=0, cursor='hand2').pack(anchor='w', padx=20, pady=(12, 0))

    def close():
        cancel.set()
        panel.destroy()

    panel.protocol('WM_DELETE_WINDOW', close)

    def load_count():
        try:
            items.put(('count', gh.star_count()))
        except Exception:
            items.put(('count', None))

    threading.Thread(target=load_count, daemon=True).start()

    def poll():
        if not panel.winfo_exists():
            return
        try:
            while True:
                kind, value = items.get_nowait()
                if kind == 'count':
                    count.configure(text=f'⭐ {value}' if value is not None else '⭐ —')
                elif kind == 'code':
                    code, url = value
                    try:
                        panel.clipboard_clear(); panel.clipboard_append(code)
                        status.configure(text=f'授权码 {code} 已复制；请在浏览器粘贴。')
                    except tk.TclError:
                        status.configure(text=f'请在浏览器输入授权码 {code}')
                    webbrowser.open(url)
                elif kind == 'verified':
                    verified[0] = True
                    working[0] = False
                    star_button.configure(text='⭐ Starred', bg='#21854d')
                    status.configure(text='已由 GitHub 确认 Star，谢谢支持！')
                elif kind == 'fallback':
                    working[0] = False
                    fallback()
        except queue.Empty:
            pass
        panel.after(200, poll)

    poll()
    return panel
