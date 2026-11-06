# -*- coding: utf-8 -*-
"""VIP充值窗口。

按需求这是个"象征性"的充值：点一下立刻免费开通，不掏钱、不接支付。
真实项目里这个位置就是调起微信/支付宝支付的地方——
支付回调成功后再调 store.recharge_vip() 就行，流程已经留好了。
"""
import tkinter as tk
from tkinter import ttk, messagebox


def open_vip_dialog(parent, store, user, on_change=None):
    """弹出VIP充值窗口。

    store: UserStore实例
    user:  当前登录的User；没登录就传None，会提示先去登录
    on_change: 开通成功后的回调（用来刷新主界面显示）
    """
    if user is None:
        messagebox.showinfo("请先登录", "开通VIP需要先登录账号。", parent=parent)
        return
    if user.is_vip:
        messagebox.showinfo("已是VIP", f"{user.username}，你已经是VIP了，尽情使用吧。", parent=parent)
        return

    win = tk.Toplevel(parent)
    win.title("开通VIP会员")
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()

    body = ttk.Frame(win, padding=24)
    body.pack(fill="both", expand=True)

    ttk.Label(body, text="VIP 会员", font=("微软雅黑", 18, "bold"),
              foreground="#c8961e").pack(pady=(0, 10))

    perks = (
        "· 视频剪辑：截取片段、画面调色、导出新视频\n"
        "· 图片高级编辑：参数调节、美图、魔法消除\n"
        "· 后续新增的高级功能默认对VIP开放\n"
        "· 支持开发者持续更新（并不，现在是免费送）"
    )
    ttk.Label(body, text=perks, justify="left",
              font=("微软雅黑", 10)).pack(pady=(0, 14))

    price = ttk.Label(body, text="限时价：￥0.00", font=("微软雅黑", 14, "bold"),
                      foreground="#d4380d")
    price.pack(pady=(0, 14))

    def do_recharge():
        if store.recharge_vip(user.username):
            messagebox.showinfo("开通成功",
                                "恭喜，VIP已开通！当前为限时免费活动。",
                                parent=win)
            user.is_vip = True
            win.destroy()
            if on_change:
                on_change()
        else:
            messagebox.showerror("出错了", "开通失败，账号数据有问题。", parent=win)

    ttk.Button(body, text="立即充值（当前免费）",
               command=do_recharge).pack(fill="x")
    ttk.Button(body, text="再想想", command=win.destroy).pack(fill="x", pady=(6, 0))
