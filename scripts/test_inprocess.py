"""Exercise the real compose button without starting Codex or child processes."""
import ctypes
from ctypes import wintypes
import json
import os
import sys
import tempfile
import time
import tkinter as tk
import uuid
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager
from PIL import Image, ImageGrab
import app
import plan_dialog
import tray
from window_ui import window_handle,minimize,TaskPicker

thread='00000000-0000-0000-0000-000000000001'
@contextmanager
def connection(*args):
    yield lambda *args:{'data':[{'id':thread,'name':'Integration task'},{'id':'00000000-0000-0000-0000-000000000002','preview':'很长的任务摘要，不应该占据输入区。\n'*100}]}
def walk(widget):
    yield widget
    for child in widget.winfo_children():yield from walk(child)
def button(widget,text):
    return next(w for w in walk(widget) if isinstance(w,tk.Button) and w.cget('text')==text)
original=tk.Tk.mainloop
errors=[]
def loop(root,*args,**kwargs):
    root.report_callback_exception=lambda kind,error,tb:errors.append(error)
    def check():
        try:
            update_button=button(root,'检查更新')
            star_button=button(root,'\u2003\u2003Star')
            assert update_button.winfo_viewable() and star_button.winfo_viewable()
            assert update_button.fill=='#2d6acb'
            update_button.configure(bg=None,text='版本')
            assert update_button.fill is None and update_button.cget('text')=='版本'
            assert star_button.cget('fg')=='#f7c948'
            assert star_button.prefix_icon.size==(20,20)
            assert any(star_button.prefix_icon.getchannel('A').histogram()[1:255])
            assert star_button.winfo_width()<=80
            assert update_button.winfo_rootx()<star_button.winfo_rootx()
            assert star_button.winfo_rooty()+star_button.winfo_height()<=root.winfo_rooty()+root.winfo_height()
            assert not any(w.cget('text')=='关于' for w in walk(root) if isinstance(w,tk.Button))
            with patch.object(app.webbrowser,'open',return_value=True) as opened:
                star_button.invoke()
                assert opened.call_args.args==(app.github_star.REPO_URL,)
            started=time.perf_counter()
            assert root.tray.hwnd.value==window_handle(root).value
            assert len([w for w in root.winfo_children() if isinstance(w,tk.Toplevel)])==1, 'Quota event should open the composer automatically'
            button(root,'打开需求输入框').invoke();root.update()
            dialogs=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel)]
            assert len(dialogs)==1
            dialog=dialogs[0]
            labels=[w.cget('text') for w in walk(dialog) if isinstance(w,tk.Label)]
            assert any(text.startswith('Integration task\n\n') for text in labels) == (sys.platform!='win32')
            assert thread not in '\n'.join(labels)
            assert dialog.title()=='Integration task'
            assert 'Integration task' in labels
            elapsed=time.perf_counter()-started
            assert dialog.winfo_viewable() and dialog.tk is root.tk
            main_rect=wintypes.RECT();child_rect=wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(window_handle(root),ctypes.byref(main_rect))
            ctypes.windll.user32.GetWindowRect(window_handle(dialog),ctypes.byref(child_rect))
            assert child_rect.top==main_rect.top
            assert child_rect.left==main_rect.right+6 or child_rect.right==main_rect.left-6
            pid=ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(window_handle(dialog),ctypes.byref(pid))
            assert pid.value==os.getpid()
            button(root,'打开需求输入框').invoke();root.update()
            assert len([w for w in root.winfo_children() if isinstance(w,tk.Toplevel)])==1
            assert not launch.called,'Opening a composer must not spawn a process'
            picker=next(w for w in walk(root) if isinstance(w,TaskPicker))
            picker.toggle();root.update()
            assert picker.button.winfo_width()==picker.panel.winfo_width(),(picker.button.winfo_width(),picker.panel.winfo_width())
            picker.hide()
            picker.current(1);button(root,'打开需求输入框').invoke();root.update()
            others=[w for w in root.winfo_children() if isinstance(w,tk.Toplevel) and w!=dialog]
            assert len(others)==1 and others[0].tk is root.tk
            rects=[]
            for window in (root,dialog,others[0]):
                bounds=wintypes.RECT()
                ctypes.windll.user32.GetWindowRect(window_handle(window),ctypes.byref(bounds))
                rects.append((bounds.left,bounds.top,bounds.right,bounds.bottom))
            for index,(left,top,right,bottom) in enumerate(rects):
                for l,t,r,b in rects[:index]:
                    assert right+6<=l or r+6<=left or bottom+6<=t or b+6<=top,rects
            assert all(r[0]>=rects[0][2]+6 for r in rects[1:]) or all(r[2]+6<=rects[0][0] for r in rects[1:])
            long_dialog=others[0]
            assert long_dialog.title().startswith('很长的任务摘要，不应该占据输入区。 ')
            heading=next(w for w in walk(long_dialog) if isinstance(w,tk.Label) and w.cget('text').startswith('很长的任务摘要') and w.winfo_name()!='placeholder')
            assert heading.cget('text').endswith('…')
            assert heading.winfo_height()<50
            for action in ('×','—'):
                control=button(long_dialog,action)
                assert control.winfo_viewable()
                assert heading.winfo_rootx()+heading.winfo_width()<=control.winfo_rootx()
                assert control.winfo_rootx()+control.winfo_width()<=long_dialog.winfo_rootx()+long_dialog.winfo_width()
            long_editor=next(w for w in walk(long_dialog) if isinstance(w,tk.Text))
            assert long_editor.winfo_viewable() and long_editor.winfo_height()>=100
            for action in ('保存','发送','+'):
                control=button(long_dialog,action)
                assert control.winfo_viewable()
                assert control.winfo_rooty()+control.winfo_height()<=long_dialog.winfo_rooty()+long_dialog.winfo_height()
            long_editor.insert('1.0','这里可以直接输入需求；任务摘要再长，也不会挤掉输入框。')
            root.update()
            evidence=Path(__file__).resolve().parent.parent/'build'/'composer-long-preview.png'
            evidence.parent.mkdir(exist_ok=True)
            x,y=long_dialog.winfo_rootx(),long_dialog.winfo_rooty()
            ImageGrab.grab((x,y,x+long_dialog.winfo_width(),y+long_dialog.winfo_height())).save(evidence)
            with patch.object(plan_dialog.messagebox,'askyesnocancel',return_value=False):
                button(others[0],'×').invoke()
            root.update()
            assert dialog.winfo_exists()
            picker.current(0)
            editor=next(w for w in walk(dialog) if isinstance(w,tk.Text))
            editor.insert('1.0','Keep draft')
            button(dialog,'↗').invoke();root.update()
            expanded=next(w for w in dialog.winfo_children() if isinstance(w,tk.Toplevel))
            assert expanded.title()=='Integration task — 编辑后续需求'
            assert any(isinstance(w,tk.Label) and w.cget('text')=='Integration task' for w in walk(expanded))
            large=next(w for w in walk(expanded) if isinstance(w,tk.Text))
            assert large.get('1.0','end-1c')=='Keep draft' and editor.cget('state')=='disabled'
            large.insert('end',' expanded')
            button(expanded,'×').invoke();root.update()
            assert editor.get('1.0','end-1c')=='Keep draft expanded'
            editor.focus_force();root.update()
            with patch.object(plan_dialog.ImageGrab,'grabclipboard',return_value=Image.new('RGB',(80,60),'green')):
                for _ in range(8):editor.event_generate('<Control-v>');root.update()
            button(dialog,'+').invoke();root.update()
            with patch.object(plan_dialog.filedialog,'askopenfilenames',return_value=[str(source)]):
                button(dialog,'添加文件').invoke()
            minimize(dialog);root.update()
            button(root,'打开需求输入框').invoke();root.update()
            assert not ctypes.windll.user32.IsIconic(window_handle(dialog))
            assert editor.get('1.0','end').strip()=='Keep draft expanded'
            button(dialog,'↗').invoke();root.update()
            colors=[]
            configure=picker.flag.itemconfigure
            def record_flag(item,**options):
                if 'fill' in options:colors.append(options['fill'])
                return configure(item,**options)
            picker.flag.itemconfigure=record_flag
            button(dialog,'保存').invoke()
            data=json.loads((folder/'followups'/f'{thread}.json').read_text(encoding='utf-8'))
            assert data['text']=='Keep draft expanded' and len(data['images'])==8 and len(data['files'])==1
            assert data['taskName']=='Integration task' and picker.pending
            ready=tk.BooleanVar();root.after(2800,lambda:ready.set(True));root.wait_variable(ready)
            assert picker.pending and picker.flag.itemcget(picker.flag_shape,'fill')=='#ef5350'
            assert picker.flag_timer is None and picker.flag.winfo_ismapped()
            assert colors.count('#43c77a')==5,colors
            data['status']='sent'
            (folder/'followups'/f'{thread}.json').write_text(json.dumps(data),encoding='utf-8')
            root.after(1100,lambda:ready.set(False));root.wait_variable(ready)
            assert not picker.pending and not picker.flag.winfo_ismapped()
            button(root,'打开需求输入框').invoke();root.update()
            dialog=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
            draft=next(w for w in walk(dialog) if isinstance(w,tk.Text))
            draft.insert('1.0','Keep draft on tray exit')
            button(root,'×').invoke();root.update()
            assert root.state()=='withdrawn' and dialog.winfo_exists()
            assert root.tray.active and root.state()=='withdrawn'
            root.tray.restore();root.update()
            root.tray.broadcast(2)
            root.after(300,lambda:ready.set(True));root.wait_variable(ready)
            assert root.state()=='withdrawn' and dialog.winfo_exists()
            assert draft.get('1.0','end-1c')=='Keep draft on tray exit'
            with patch.object(plan_dialog.messagebox,'askyesnocancel',return_value=False):
                button(dialog,'×').invoke()
            assert root.tray.closed and not root.tray.active
            print(f'INPROCESS_OK: {elapsed*1000:.0f} ms, same PID, task name, fixed width, expanded editor, 8 images, saved/sent flag, close/save')
        except Exception as error:
            errors.append(error)
            try:root.destroy()
            except tk.TclError:pass
    root.after(4000,check)
    return original(root,*args,**kwargs)
with tempfile.TemporaryDirectory() as directory:
    folder=Path(directory);source=folder/'sample.txt';source.write_text('local file',encoding='utf-8')
    with patch.object(tray,'GROUP','CodexQuotaResume.Test.'+uuid.uuid4().hex),patch.object(app.w,'latest_candidate',return_value={'threadId':thread,'key':'test-quota','quotaError':True}),patch.object(app.w,'APP_DIR',folder),patch.object(app.w,'load_state',return_value={}),patch.object(app.w,'find_codex',return_value='codex'),patch.object(app.w.codex_status,'connection',connection),patch.object(app,'monitor_indicator',return_value=('', '', True)),patch.object(app.updater,'check_windows_update',return_value=True),patch.object(app.github_star,'star_count',return_value=None),patch.object(app.subprocess,'Popen') as launch,patch.object(tk.Tk,'mainloop',loop):
        app.show()
assert not errors,errors
