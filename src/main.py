# -*- coding: utf-8 -*-
"""光影工坊 PhotoStudio 程序入口。

跑法：python src/main.py
"""
import tkinter as tk

from photostudio.auth import UserStore
from photostudio.config import APP_NAME, VERSION
from photostudio.login_window import LoginWindow
from photostudio.main_window import MainWindow


def main():
    root = tk.Tk()
    root.title(f"{APP_NAME} v{VERSION}")

    win = MainWindow(root)
    win.set_store(UserStore())   # 用户数据从这里注入，以后换服务器实现也在这换

    # 启动先弹登录窗，不想登录点"游客模式"也能进去看图
    LoginWindow(root, win.store, on_login=win.set_user)

    root.mainloop()


if __name__ == "__main__":
    main()
