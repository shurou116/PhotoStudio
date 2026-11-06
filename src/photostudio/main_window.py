# -*- coding: utf-8 -*-
"""主窗口：看图 + 所有功能的入口。

布局从上到下：菜单栏 -> 工具栏 -> 中间（左边文件列表 + 右边画布）-> 状态栏。

权限规则（按需求定的）：
  游客：只能看图
  登录用户：图片编辑（参数/美图/人脸/魔法消除）
  VIP：以上全部 + 视频剪辑
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import ImageTk

from . import image_ops as ops
from .config import APP_NAME, VERSION, AUTHOR, EMAIL, manual_path
from .login_window import LoginWindow
from .vip_dialog import open_vip_dialog


class MainWindow:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.store = None        # UserStore，由main.py注入
        self.user = None         # 当前用户，None表示游客

        self.image_paths = []    # 当前文件夹里的图片路径列表
        self.index = -1          # 当前看到第几张
        self.cv_img = None       # 当前图片的BGR ndarray

        self.scale = 1.0         # 显示缩放倍数
        self.offset_x = 0        # 图片在画布上的偏移（用于拖动平移）
        self.offset_y = 0
        self._tk_photo = None    # 持有引用防止被GC回收，一回收图就消失

        root.title(f"{APP_NAME} v{VERSION}")
        root.geometry("1100x700")
        root.minsize(860, 560)

        self._build_menu()
        self._build_toolbar()
        self._build_body()
        self._build_statusbar()
        self._bind_events()

    # ==================== 界面搭建 ====================

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label="打开图片...", command=self.open_image)
        m_file.add_command(label="打开文件夹...", command=self.open_folder)
        m_file.add_separator()
        m_file.add_command(label="退出", command=self.root.destroy)
        menubar.add_cascade(label="文件", menu=m_file)

        m_account = tk.Menu(menubar, tearoff=0)
        m_account.add_command(label="登录 / 注册", command=self.show_login)
        m_account.add_command(label="充值VIP", command=self.show_vip)
        m_account.add_command(label="退出登录", command=self.logout)
        menubar.add_cascade(label="账户", menu=m_account)

        m_tool = tk.Menu(menubar, tearoff=0)
        m_tool.add_command(label="编辑图片（需登录）", command=self.open_editor)
        m_tool.add_command(label="视频剪辑（需VIP）", command=self.open_video)
        menubar.add_cascade(label="工具", menu=m_tool)

        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label="操作手册", command=self.open_manual)
        m_help.add_command(label="关于", command=self.show_about)
        menubar.add_cascade(label="帮助", menu=m_help)

        self.root.config(menu=menubar)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.pack(fill="x")

        def add_btn(text, cmd):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=3)

        add_btn("打开图片", self.open_image)
        add_btn("打开文件夹", self.open_folder)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        add_btn("◀ 上一张", self.prev_image)
        add_btn("下一张 ▶", self.next_image)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        add_btn("编辑图片", self.open_editor)
        add_btn("视频剪辑", self.open_video)
        add_btn("充值VIP", self.show_vip)

    def _build_body(self):
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True)

        # 左侧文件列表
        listframe = ttk.Frame(body, width=220)
        listframe.pack(side="left", fill="y", padx=(6, 0), pady=6)
        ttk.Label(listframe, text="图片列表", padding=4).pack(fill="x")
        self.file_list = tk.Listbox(listframe, activestyle="dotbox")
        self.file_list.pack(fill="both", expand=True)
        self.file_list.bind("<<ListboxSelect>>", self._on_list_select)

        # 右边画布，底色用中性灰，看图不刺眼
        self.canvas = tk.Canvas(body, bg="#3c3f41",
                                highlightthickness=0, cursor="fleur")
        self.canvas.pack(side="left", fill="both", expand=True,
                         padx=6, pady=6)

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, padding=(8, 3))
        bar.pack(fill="x")
        self.status_user = ttk.Label(bar, text="未登录")
        self.status_user.pack(side="left")
        self.status_img = ttk.Label(bar, text="没有打开图片")
        self.status_img.pack(side="right")

    def _bind_events(self):
        # 鼠标滚轮缩放。Windows上滚轮事件绑在root上才收得到
        self.root.bind("<MouseWheel>", lambda e: self._zoom(-e.delta / 1200))
        # 左键拖动平移图片
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        # 左右方向键翻页
        self.root.bind("<Left>", lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())

    # ==================== 账户相关 ====================

    def set_store(self, store):
        self.store = store

    def set_user(self, user):
        self.user = user
        if user:
            vip = " [VIP]" if user.is_vip else ""
            self.status_user.config(text=f"用户：{user.username}{vip}")
        else:
            self.status_user.config(text="未登录（游客模式）")

    def show_login(self):
        LoginWindow(self.root, self.store, on_login=self.set_user)

    def show_vip(self):
        open_vip_dialog(self.root, self.store, self.user,
                        on_change=lambda: self.set_user(self.user))

    def logout(self):
        if self.user is None:
            messagebox.showinfo("提示", "你本来就还没登录。", parent=self.root)
            return
        if messagebox.askyesno("退出登录", "确定要退出登录吗？"):
            self.set_user(None)

    # ==================== 文件打开与浏览 ====================

    def open_image(self):
        path = filedialog.askopenfilename(
            title="打开图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp *.gif *.tif *.tiff"),
                       ("所有文件", "*.*")])
        if not path:
            return
        folder = os.path.dirname(path)
        # 打开单张图时，把它所在文件夹也加载进列表，方便前后翻页
        self._load_folder(folder, select=path)

    def open_folder(self):
        folder = filedialog.askdirectory(title="打开文件夹")
        if folder:
            self._load_folder(folder)

    def _load_folder(self, folder, select=None):
        names = sorted(os.listdir(folder))
        paths = [os.path.join(folder, n) for n in names
                 if os.path.splitext(n)[1].lower() in ops.IMAGE_EXTS]
        if not paths:
            messagebox.showinfo("提示", "这个文件夹里没有图片。", parent=self.root)
            return

        self.image_paths = paths
        self.file_list.delete(0, "end")
        for p in paths:
            self.file_list.insert("end", os.path.basename(p))

        if select and select in paths:
            self._show_index(paths.index(select))
        else:
            self._show_index(0)

    def _on_list_select(self, event):
        sel = self.file_list.curselection()
        if sel:
            self._show_index(sel[0])

    def prev_image(self):
        if self.image_paths:
            self._show_index((self.index - 1) % len(self.image_paths))

    def next_image(self):
        if self.image_paths:
            self._show_index((self.index + 1) % len(self.image_paths))

    def _show_index(self, idx):
        idx %= len(self.image_paths)
        path = self.image_paths[idx]
        try:
            img = ops.load_image(path)
        except Exception as e:
            messagebox.showerror("打不开", f"这张图读不出来：\n{path}\n\n{e}",
                                 parent=self.root)
            return
        self.index = idx
        self.cv_img = img
        # 同步左侧列表的高亮
        self.file_list.selection_clear(0, "end")
        self.file_list.selection_set(idx)
        self.file_list.see(idx)

        h, w = img.shape[:2]
        size_kb = os.path.getsize(path) / 1024
        self.status_img.config(
            text=f"{os.path.basename(path)}  {w}×{h}  {size_kb:.0f} KB")
        self._fit_to_window()

    # ==================== 画布显示 ====================

    def _fit_to_window(self):
        """按窗口大小自适应缩放。"""
        if self.cv_img is None:
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10:      # 窗口还没真正渲染出来，等一下再算
            self.canvas.after(50, self._fit_to_window)
            return
        h, w = self.cv_img.shape[:2]
        self.scale = min(cw / w, ch / h, 1.0)   # 不放超过100%，原图细节不骗人
        self.offset_x = (cw - w * self.scale) / 2
        self.offset_y = (ch - h * self.scale) / 2
        self._render()

    def _render(self):
        """把当前图按scale缩放后画到画布中央。"""
        if self.cv_img is None:
            return
        h, w = self.cv_img.shape[:2]
        dw, dh = max(1, int(w * self.scale)), max(1, int(h * self.scale))

        pil = ops.to_pil(self.cv_img).resize((dw, dh))
        self._tk_photo = ImageTk.PhotoImage(pil)

        self.canvas.delete("all")
        self.canvas.create_image(self.offset_x, self.offset_y,
                                 anchor="nw", image=self._tk_photo)

    def _zoom(self, amount):
        """滚轮缩放，以画布中心为基准。"""
        if self.cv_img is None:
            return
        old = self.scale
        self.scale = max(0.05, min(8.0, self.scale * (1 + amount)))
        if abs(self.scale - old) < 1e-9:
            return
        # 让缩放围绕画布中心，而不是图片左上角
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        self.offset_x = cw / 2 - (cw / 2 - self.offset_x) * self.scale / old
        self.offset_y = ch / 2 - (ch / 2 - self.offset_y) * self.scale / old
        self._render()

    def _on_drag_start(self, event):
        self._drag_origin = (event.x, event.y)

    def _on_drag_move(self, event):
        if self.cv_img is None:
            return
        dx = event.x - self._drag_origin[0]
        dy = event.y - self._drag_origin[1]
        self._drag_origin = (event.x, event.y)
        self.offset_x += dx
        self.offset_y += dy
        self.canvas.move("all", dx, dy)

    # ==================== 功能入口（带权限拦截） ====================

    def open_editor(self):
        if self.cv_img is None:
            messagebox.showinfo("提示", "先打开一张图片再编辑。", parent=self.root)
            return
        if self.user is None:
            if messagebox.askyesno("需要登录",
                                   "编辑功能需要登录后使用。\n现在去登录吗？"):
                self.show_login()
            if self.user is None:   # 登录窗口关了还是游客，就别进编辑器了
                return
        # 延迟导入，程序启动更快，而且编辑器出问题也不影响看图
        from .editor_window import EditorWindow
        EditorWindow(self.root, self.cv_img,
                     os.path.basename(self.image_paths[self.index]),
                     on_save=self._on_editor_save)

    def _on_editor_save(self, img):
        """编辑器里点了"完成"后，刷新主窗口显示。"""
        self.cv_img = img
        h, w = img.shape[:2]
        self.status_img.config(text=f"{self.status_img.cget('text').split('  ')[0]}"
                                    f"  {w}×{h}  （已编辑）")
        self._fit_to_window()

    def open_video(self):
        if self.user is None:
            if messagebox.askyesno("需要登录",
                                   "视频剪辑是VIP功能，需要先登录。\n现在去登录吗？"):
                self.show_login()
            if self.user is None:
                return
        if not self.user.is_vip:
            open_vip_dialog(self.root, self.store, self.user,
                            on_change=lambda: self.set_user(self.user))
            if not self.user.is_vip:   # 还是没开通就不进去了
                return
        from .video_window import VideoWindow
        VideoWindow(self.root)

    # ==================== 帮助 ====================

    def open_manual(self):
        path = manual_path()
        if path is None:
            messagebox.showwarning("找不到手册",
                                   "操作手册文件丢了（docs/操作手册.txt）。",
                                   parent=self.root)
            return
        # 用系统默认程序打开txt，记事本什么的都行
        os.startfile(path)

    def show_about(self):
        messagebox.showinfo(
            "关于",
            f"{APP_NAME} PhotoStudio v{VERSION}\n\n"
            f"一个能看图、修图、剪视频的小工具。\n\n"
            f"作者：{AUTHOR}\n邮箱：{EMAIL}",
            parent=self.root)
