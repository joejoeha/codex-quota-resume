"""Shared rounded desktop window and draggable non-input surfaces."""
import tkinter as tk
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path
from tkinter import font as tkfont
from PIL import Image, ImageDraw, ImageTk

FONT_FAMILY = 'PingFang SC' if sys.platform == 'darwin' else 'Microsoft YaHei UI'


class RoundedButton(tk.Button):
    """Keep native button keyboard/command behavior with a rounded image surface."""
    def __init__(self, parent, *, text='', command=None, bg='#2b2b2b', fg='#eeeeee',
                 font=(FONT_FAMILY, 11), padx=14, pady=10, image=None, width_px=None, prefix_icon=None):
        self.fixed_width=width_px
        self.fill=bg
        self.padding=(padx,pady)
        self.content_image=image
        self.prefix_icon=prefix_icon
        super().__init__(parent,text=text,command=command,font=font,fg=fg,
                         bg=parent.cget('bg'),activebackground=parent.cget('bg'),
                         activeforeground=fg,relief='flat',bd=0,highlightthickness=0,
                         highlightbackground=parent.cget('bg'),
                         padx=0,pady=0,cursor='hand2',compound='center',takefocus=False)
        self.bind('<ButtonPress-1>',self._mouse_press)
        self.bind('<ButtonRelease-1>',self._mouse_release)
        self.bind('<Enter>',lambda e:self.redraw(True))
        self.bind('<Leave>',lambda e:self.redraw())
        self.bind('<FocusIn>',lambda e:self.redraw())
        self.bind('<FocusOut>',lambda e:self.redraw())
        self.redraw()

    def _mouse_press(self, event):
        self.winfo_toplevel().focus_set()
        return 'break'

    def _mouse_release(self, event):
        if 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.invoke()
        self.winfo_toplevel().focus_set()
        return 'break'

    def redraw(self,hover=False):
        font=tkfont.Font(font=self.cget('font'))
        px,py=self.padding
        content=self.content_image
        icon=self.prefix_icon
        text_width=font.measure(self.cget('text'))+(icon.width if icon and not self.cget('text').strip() else 0)
        width=self.fixed_width or (content.width if content else text_width)+2*px
        height=max(content.height if content else font.metrics('linespace'),icon.height if icon else 0)+2*py
        color=self.fill
        if hover and color:
            color='#'+''.join(f'{min(255,int(color[i:i+2],16)+16):02x}' for i in (1,3,5))
        background=tuple(v//257 for v in self.winfo_rgb(self.master.cget('bg')))
        surface=Image.new('RGB',(width*3,height*3),background)
        draw=ImageDraw.Draw(surface)
        if color or (self.focus_get()==self and self.cget('takefocus')!='0'):
            draw.rounded_rectangle((1,1,width*3-2,height*3-2),radius=30,fill=color,
                                   outline='#8ab4f8' if self.focus_get()==self and self.cget('takefocus')!='0' else color,width=3)
        surface=surface.resize((width,height),Image.Resampling.LANCZOS)
        if content:surface.paste(content,(px,py))
        if icon:surface.paste(icon,(px,(height-icon.height)//2),icon if icon.mode=='RGBA' else None)
        self.surface=ImageTk.PhotoImage(surface,master=self)
        super().configure(image=self.surface)

    def set_surface_background(self,color):
        super().configure(bg=color,activebackground=color,highlightbackground=color)

    def configure(self,cnf=None,**kwargs):
        if cnf is not None:return super().configure(cnf,**kwargs)
        if 'bg' in kwargs:self.fill=kwargs.pop('bg')
        result=super().configure(**kwargs)
        self.redraw()
        return result

    config=configure


class TaskPicker(tk.Frame):
    """Task list using the same rounded surfaces as the composer."""
    def __init__(self,parent,font):
        super().__init__(parent,bg=parent.cget('bg'))
        self.values=[]
        self.index=-1
        self.button=RoundedButton(self,text='选择任务  ▾',font=font,command=self.toggle,width_px=374)
        self.button.pack(fill='x')
        self.flag=tk.Canvas(self,width=24,height=26,bg='#2b2b2b',highlightthickness=0)
        self.flag.create_line(5,3,5,24,fill='#dddddd',width=2)
        self.flag_shape=self.flag.create_polygon(6,3,21,3,17,9,21,15,6,15,fill='#ef5350',outline='')
        self.flag_timer=None
        self.pending=False
        self.bind('<Destroy>',self.cancel_flag,add='+')
        self.panel=tk.Canvas(parent,width=374,height=212,bg=parent.cget('bg'),highlightthickness=0)
        self.panel.create_polygon(20,1,354,1,373,1,373,20,373,192,373,211,354,211,
                                  20,211,1,211,1,192,1,20,1,1,smooth=True,
                                  fill='#242424',outline='#383838')
        interior=tk.Frame(self.panel,bg='#242424')
        self.panel.create_window(10,10,anchor='nw',width=354,height=192,window=interior)
        self.listing=tk.Listbox(interior,bg='#242424',fg='#eeeeee',selectbackground='#383838',
                               selectforeground='white',font=font,relief='flat',bd=0,
                               highlightthickness=0,exportselection=False,activestyle='none')
        from tkinter import ttk
        scroll=ttk.Scrollbar(interior,command=self.listing.yview)
        scroll.pack(side='right',fill='y')
        self.listing.configure(yscrollcommand=scroll.set)
        self.listing.pack(fill='both',expand=True)
        self.listing.bind('<ButtonRelease-1>',self.choose)
        self.listing.bind('<Return>',self.choose)
        self.listing.bind('<Escape>',lambda e:self.hide(keyboard=True))
        self.winfo_toplevel().bind('<Button-1>',self.dismiss,add='+')

    def cancel_flag(self,event=None):
        if event is not None and event.widget!=self:return
        if self.flag_timer:self.after_cancel(self.flag_timer);self.flag_timer=None

    def set_pending(self,pending,blink=False):
        self.pending=pending
        if not pending:
            self.cancel_flag();self.flag.place_forget();return
        self.flag.place(relx=1,x=-35,y=8)
        tk.Misc.lift(self.flag)
        if blink:
            self.cancel_flag()
            self.flash_flag(0)
        elif self.flag_timer is None:self.flag.itemconfigure(self.flag_shape,fill='#ef5350')

    def flash_flag(self,step):
        self.flag_timer=None
        if not self.pending:return
        self.flag.itemconfigure(self.flag_shape,fill='#43c77a' if step%2==0 and step<10 else '#ef5350')
        if step<10:self.flag_timer=self.after(250,lambda:self.flash_flag(step+1))

    def set_values(self,values):
        self.values=list(values)
        self.listing.delete(0,'end')
        for value in self.values:self.listing.insert('end',value)
        self.current(0 if self.values else -1)

    def current(self,index=None):
        if index is None:return self.index
        self.index=index
        text=self.values[index] if 0<=index<len(self.values) else '选择任务'
        font=tkfont.Font(font=self.button.cget('font'))
        while font.measure(text)>260:text=text[:-2]+'…'
        self.button.configure(text=text+'  ▾')

    def toggle(self):
        if self.panel.winfo_ismapped():self.hide();return
        self.panel.place(x=self.winfo_x(),y=max(0,self.winfo_y()-220))
        tk.Misc.lift(self.panel)
        self.listing.selection_clear(0,'end')
        if self.index>=0:
            self.listing.selection_set(self.index);self.listing.activate(self.index);self.listing.see(self.index)
        self.listing.focus_set()

    def hide(self,keyboard=False):
        self.panel.place_forget()
        (self.button if keyboard else self.winfo_toplevel()).focus_set()

    def choose(self,event=None):
        selection=self.listing.curselection()
        if selection:self.current(selection[0])
        self.hide(keyboard=event is not None and event.type==tk.EventType.KeyPress)
        return 'break'

    def dismiss(self,event):
        widget=event.widget
        while widget is not None:
            if widget in (self,self.panel):return
            widget=getattr(widget,'master',None)
        if self.panel.winfo_ismapped():self.panel.place_forget()


def window_handle(root):
    user32=ctypes.windll.user32
    user32.GetParent.restype=ctypes.c_void_p
    return ctypes.c_void_p(user32.GetParent(root.winfo_id()))


def adjacent_positions(main,child_size,work,gap=6):
    main,children=group_positions(main,child_size,work,1,gap)
    return main,children[0]


def group_positions(main,child_size,work,count,gap=6):
    """Tile composers on one side; reject layouts that cannot fit the work area."""
    x,y,width,height=main
    cw,ch=child_size
    left,top,right,bottom=work
    columns=min(count,(right-left-width)//(cw+gap))
    rows=(bottom-top+gap)//(ch+gap)
    if columns<1 or rows<1 or count>columns*rows or height>bottom-top:
        raise ValueError('当前屏幕放不下更多输入窗。请先保存并关闭一个输入窗，或最小化暂时不用的输入窗。')
    span=columns*(cw+gap)
    side=1 if x+width+span<=right else -1 if x-span>=left else (1 if right-x-width>=x-left else -1)
    x=max(left if side==1 else left+span,min(x,right-width-span if side==1 else right-width))
    used_rows=(count+columns-1)//columns
    y=max(top,min(y,bottom-max(height,used_rows*(ch+gap)-gap)))
    children=[]
    for index in range(count):
        row,column=divmod(index,columns)
        cx=x+width+gap+column*(cw+gap) if side==1 else x-(column+1)*(cw+gap)
        children.append((cx,y+row*(ch+gap)))
    return (x,y),children


def place_beside(dialog,parent):
    """Arrange all visible composers; dialog=None only checks room for a new one."""
    if sys.platform == 'darwin':
        from macos import work_area
        parent.update_idletasks()
        x,y=parent.winfo_x(),parent.winfo_y()
        width,height=parent.window_size
        dialogs=[item for item in parent.winfo_children() if getattr(item,'is_task_composer',False)
                 and (item is dialog or item.state()=='normal')]
        if dialog not in dialogs:dialogs.append(dialog)
        size=dialog.window_size if dialog is not None else (430,535)
        main,children=group_positions((x,y,width,height),size,
                                       work_area(x+width//2,y+height//2),len(dialogs))
        if dialog is None:return
        parent.geometry(f'+{main[0]}+{main[1]}')
        for item,position in zip(dialogs,children):
            item.geometry(f'+{position[0]}+{position[1]}')
        return
    class MonitorInfo(ctypes.Structure):
        _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),
                  ('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]
    user32=ctypes.windll.user32
    user32.MonitorFromWindow.restype=ctypes.c_void_p
    parent_handle=window_handle(parent)
    rect=wintypes.RECT()
    if not user32.GetWindowRect(parent_handle,ctypes.byref(rect)):raise ctypes.WinError()
    monitor=ctypes.c_void_p(user32.MonitorFromWindow(parent_handle,2))
    info=MonitorInfo();info.cbSize=ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(monitor,ctypes.byref(info)):raise ctypes.WinError()
    work=info.rcWork
    original=(rect.left,rect.top)
    dialogs=[item for item in parent.winfo_children() if getattr(item,'is_task_composer',False)
             and (item is dialog or (item.state()!='withdrawn' and not user32.IsIconic(window_handle(item))))]
    if dialog not in dialogs:dialogs.append(dialog)
    size=dialog.window_size if dialog is not None else (430,535)
    main,children=group_positions((*original,rect.right-rect.left,rect.bottom-rect.top),
                                  size,(work.left,work.top,work.right,work.bottom),len(dialogs))
    if dialog is None:return
    if main!=original:user32.SetWindowPos(parent_handle,None,*main,0,0,0x15)
    for item,position in zip(dialogs,children):
        user32.SetWindowPos(window_handle(item),None,*position,*item.window_size,0x14)


def minimize(root):
    if sys.platform == 'darwin':
        root.overrideredirect(False)
        def mapped(event):
            if event.widget == root and root.state() == 'normal':
                root.overrideredirect(True)
                root.unbind('<Map>',binding)
        binding=root.bind('<Map>',mapped,add='+')
        root.iconify()
        return
    configure_taskbar(root)
    ctypes.windll.user32.ShowWindow(window_handle(root),6)


def window_controls(root,parent,font,on_close=None,on_minimize=None):
    for text,command in [('×',on_close or root.destroy),('—',on_minimize or (lambda:minimize(root)))]:
        RoundedButton(parent,text=text,command=command,font=font,padx=16,pady=8).pack(side='right',padx=(6,0))


def configure_taskbar(root):
    if sys.platform == 'darwin':return
    user32=ctypes.windll.user32
    hwnd=window_handle(root)
    style=user32.GetWindowLongW(hwnd,-20)
    user32.SetWindowLongW(hwnd,-20,(style | 0x40000) & ~0x80)
    user32.SetWindowPos(hwnd,None,0,0,0,0,0x37)
    icon=Path(__file__).with_name('app-icon.ico')
    if not icon.exists():icon=Path(__file__).parent.parent/'assets'/'app-icon.ico'
    if icon.exists():root.iconbitmap(str(icon))


def bind_drag(root, *widgets):
    offset=[0,0]
    def start(event):
        offset[:]=[event.x_root-root.winfo_x(),event.y_root-root.winfo_y()]
    def move(event):
        if sys.platform == 'darwin':
            root.geometry(f'+{event.x_root-offset[0]}+{event.y_root-offset[1]}')
            return
        ctypes.windll.user32.SetWindowPos(window_handle(root),None,event.x_root-offset[0],event.y_root-offset[1],0,0,0x15)
    for widget in widgets:
        widget.bind('<ButtonPress-1>',start)
        widget.bind('<B1-Motion>',move)


def rounded_window(root,width,height):
    root.window_size=(width,height)
    if sys.platform != 'darwin':ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('CodexQuotaResume.Desktop')
    root.overrideredirect(True)
    background='systemTransparent' if sys.platform == 'darwin' else '#010203'
    root.configure(bg=background)
    if sys.platform == 'darwin':root.wm_attributes('-transparent',True)
    else:root.wm_attributes('-transparentcolor','#010203')
    root.geometry(f'{width}x{height}+{max(0,(root.winfo_screenwidth()-width)//2)}+{max(0,(root.winfo_screenheight()-height)//2)}')
    canvas=tk.Canvas(root,bg=background,highlightthickness=0)
    canvas.pack(fill='both',expand=True)
    radius=48
    shape=canvas.create_polygon(radius,1,width-radius,1,width-1,1,width-1,radius,
                          width-1,height-radius,width-1,height-1,width-radius,height-1,
                          radius,height-1,1,height-1,1,height-radius,1,radius,1,1,
                          smooth=True,fill='#181818',outline='#383838',width=1)
    body=tk.Frame(root,bg='#181818')
    root.window_canvas=canvas;root.window_shape=shape;root.window_body=body
    body.place(x=28,y=22,width=width-56,height=height-44)
    bind_drag(root,canvas,body)
    root.bind('<Map>',lambda event:root.after_idle(lambda:configure_taskbar(root)) if event.widget==root else None,add='+')
    root.after(0,lambda:configure_taskbar(root))
    if sys.platform == 'darwin':
        from macos import repaint_on_layout
        repaint_on_layout(root)
    return body
