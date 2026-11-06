# -*- coding: utf-8 -*-
"""启动时的登录/注册窗口。

一个窗口两种模式（登录/注册），右上角按钮切换，省得做两个窗口。
不想登录也可以点"游客模式"进去，但游客只能看图，编辑功能会拦下来。
"""
import tkinter as tk
from tkinter import ttk, messagebox

from .config import APP_NAME, VERSION, AUTHOR


class LoginWindow(tk.Toplevel):
    """on_login(user) 在窗口关闭时必定会被调用一次：
    登录成功传User，游客进入或直接关窗传None。"""

    def __init__(self, parent, store, on_login):
        super().__init__(parent)
        self.store = store
        self.on_login = on_login
        self._finished = False   # 防止回调被触发两次

        self.title(f"{APP_NAME} v{VERSION} - 登录")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(None))

        body = ttk.Frame(self, padding=24)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text=APP_NAME, font=("微软雅黑", 20, "bold")).pack(pady=(0, 4))
        ttk.Label(body, text=f"v{VERSION}  by {AUTHOR}", foreground="#888").pack(pady=(0, 16))

        self.var_user = tk.StringVar()
        self.var_pass = tk.StringVar()
        self.var_pass2 = tk.StringVar()

        form = ttk.Frame(body)
        form.pack()
        ttk.Label(form, text="账号").grid(row=0, column=0, sticky="e", pady=4, padx=(0, 8))
        self.ent_user = ttk.Entry(form, textvariable=self.var_user, width=24)
        self.ent_user.grid(row=0, column=1, pady=4)
        ttk.Label(form, text="密码").grid(row=1, column=0, sticky="e", pady=4, padx=(0, 8))
        self.ent_pass = ttk.Entry(form, textvariable=self.var_pass, show="*", width=24)
        self.ent_pass.grid(row=1, column=1, pady=4)

        # 确认密码这行只有注册模式才显示
        self.lab_pass2 = ttk.Label(form, text="确认密码")
        self.ent_pass2 = ttk.Entry(form, textvariable=self.var_pass2, show="*", width=24)

        self.btn_main = ttk.Button(body, text="登 录", command=self._submit)
        self.btn_main.pack(fill="x", pady=(16, 4))
        ttk.Button(body, text="游客模式（只能看图）",
                   command=lambda: self._finish(None)).pack(fill="x", pady=4)

        self.btn_switch = ttk.Button(body, text="没有账号？点这里注册",
                                     command=self._switch_mode)
        self.btn_switch.pack(pady=(8, 0))

        # 密码框里敲回车直接提交，省一次鼠标点击
        self.ent_pass.bind("<Return>", lambda e: self._submit())
        self.ent_pass2.bind("<Return>", lambda e: self._submit())

        self._mode = "login"
        self._apply_mode()

        # 模态：弹出来后主窗口点不了，必须先处理这边
        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda e: self._finish(None))

    # ---------- 内部逻辑 ----------

    def _switch_mode(self):
        self._mode = "register" if self._mode == "login" else "login"
        self._apply_mode()

    def _apply_mode(self):
        if self._mode == "login":
            self.btn_main.config(text="登 录")
            self.btn_switch.config(text="没有账号？点这里注册")
            self.lab_pass2.grid_forget()
            self.ent_pass2.grid_forget()
        else:
            self.btn_main.config(text="注 册")
            self.btn_switch.config(text="已有账号？点这里登录")
            self.lab_pass2.grid(row=2, column=0, sticky="e", pady=4, padx=(0, 8))
            self.ent_pass2.grid(row=2, column=1, pady=4)

    def _submit(self):
        username = self.var_user.get()
        password = self.var_pass.get()

        if self._mode == "register":
            if password != self.ent_pass2.get():
                messagebox.showwarning("提示", "两次输入的密码不一样", parent=self)
                return
            ok, msg = self.store.register(username, password)
            if not ok:
                messagebox.showwarning("注册失败", msg, parent=self)
                return
            user, msg = self.store.login(username, password)
        else:
            user, msg = self.store.login(username, password)

        if user is None:
            messagebox.showerror("登录失败", msg, parent=self)
            return
        self._finish(user)

    def _finish(self, user):
        if self._finished:
            return
        self._finished = True
        self.grab_release()
        self.destroy()
        self.on_login(user)
