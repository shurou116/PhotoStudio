# -*- coding: utf-8 -*-
"""冒烟测试：不开消息循环，把核心流程真刀真枪跑一遍。

跑法（在项目根目录）：
    python tests/smoke_test.py

全部通过会打印一排OK和最后的"全部通过"。
跑的时候会闪几个窗口出来，是正常的，跑完自动关。
"""
import os
import sys
import tempfile

import numpy as np

# 让tests目录也能找到src里的包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import cv2  # noqa: E402

from photostudio import image_ops as ops  # noqa: E402
from photostudio.auth import UserStore  # noqa: E402


def test_image_ops():
    img = cv2.cvtColor(np.tile(np.arange(256, dtype=np.uint8), (240, 1)),
                       cv2.COLOR_GRAY2BGR)

    outs = [
        ops.adjust_brightness(img, 30),
        ops.adjust_contrast(img, 1.5),
        ops.adjust_saturation(img, 1.3),
        ops.adjust_temperature(img, 20),
        ops.sharpen(img, 1.0),
        ops.flip(img, 1),
        ops.smooth_skin(img, 60),
        ops.whiten(img, 0.5),
        ops.auto_beauty(img),
        ops.apply_adjustments(img, {"brightness": 10, "contrast": 120,
                                    "saturation": 80, "temperature": 10,
                                    "sharpen": 30}),
        ops.inpaint(img, np.zeros(img.shape[:2], np.uint8)),
    ]
    for out in outs:
        assert out.shape == img.shape and out.dtype == np.uint8
    print("OK  image_ops 基础函数")

    r = ops.rotate(img, 1)
    assert r.shape[:2] == (img.shape[1], img.shape[0])
    c = ops.crop(img, 10, 10, 100, 100)
    assert c.shape[:2] == (90, 90) and ops.crop(img, 0, 0, 1, 1) is None
    print("OK  image_ops 旋转/裁剪")

    # 中文路径读写
    p = os.path.join(tempfile.gettempdir(), "光影工坊测试图.png")
    assert ops.save_image(ops.auto_beauty(img), p)
    assert ops.load_image(p).shape == img.shape
    print("OK  中文路径读写")

    assert ops.detect_faces(np.random.randint(0, 255, (200, 200, 3),
                                              np.uint8)) == []
    print("OK  人脸检测（噪声图不误报）")


def test_auth():
    csv_path = os.path.join(tempfile.mkdtemp(), "users.csv")
    store = UserStore(path=csv_path)

    ok, _ = store.register("张三", "123456")
    assert ok
    ok, _ = store.register("张三", "别的密码")
    assert not ok, "重复账号应该注册失败"
    ok, _ = store.register("", "")
    assert not ok

    user, _ = store.login("张三", "123456")
    assert user and user.username == "张三" and not user.is_vip
    user, _ = store.login("张三", "错的")
    assert user is None
    user, _ = store.login("不存在的人", "123456")
    assert user is None

    assert store.recharge_vip("张三")
    user, _ = store.login("张三", "123456")
    assert user.is_vip, "充值后应该是VIP"

    # 重开一次，确认落盘了
    store2 = UserStore(path=csv_path)
    user, _ = store2.login("张三", "123456")
    assert user and user.is_vip
    print("OK  用户系统（注册/登录/改密错误/充值/落盘）")


def test_gui():
    import tkinter as tk
    from photostudio.main_window import MainWindow
    from photostudio.editor_window import EditorWindow
    from photostudio.video_window import VideoWindow
    from photostudio.login_window import LoginWindow

    root = tk.Tk()
    root.withdraw()   # 主窗口藏起来，测试窗口照常跑

    # ---- 主窗口 ----
    import photostudio.main_window as mw
    saved_store_path = os.path.join(tempfile.mkdtemp(), "users.csv")
    win = MainWindow(root)
    win.set_store(UserStore(path=saved_store_path))
    win.set_user(None)
    win.set_store(UserStore(path=saved_store_path))
    UserStore(path=saved_store_path).register("测试员", "abc123")
    user, _ = UserStore(path=saved_store_path).login("测试员", "abc123")
    win.set_user(user)
    root.update()
    print("OK  主窗口构建")

    # ---- 登录窗口 ----
    login = LoginWindow(root, win.store, on_login=lambda u: None)
    root.update()
    login.var_user.set("测试员")
    login.var_pass.set("abc123")
    login._submit()
    root.update()
    print("OK  登录窗口（含真实提交）")

    # ---- 编辑器全流程 ----
    img = ops.load_image(
        os.path.join(os.path.dirname(__file__), "..", "tests", "sample.jpg")) \
        if os.path.exists(os.path.join(os.path.dirname(__file__), "sample.jpg")) \
        else np.random.randint(60, 180, (300, 400, 3), np.uint8)

    saved = {}
    ed = EditorWindow(root, img, "测试图.jpg", on_save=lambda im: saved.setdefault("img", im))
    root.update()

    ed.var_brightness.set(20)
    ed.var_contrast.set(130)
    ed._apply_adjustments()
    assert ed.work.shape == img.shape
    ed._transform(lambda im: ops.rotate(im, 1))
    assert ed.work.shape[:2] == (img.shape[1], img.shape[0])
    ed._auto_beauty()
    ed._detect_faces()          # 随机图检测不出人脸，只要不炸就行
    # 涂一块mask然后魔法消除
    ed.mask = np.zeros(ed.work.shape[:2], np.uint8)
    cv2.circle(ed.mask, (100, 100), 30, 255, -1)
    ed._do_inpaint()
    ed.undo()
    assert ed.work.shape[:2] == (img.shape[1], img.shape[0]), "撤销应回到旋转后"
    ed._finish()
    assert "img" in saved, "完成后应回调on_save"
    root.update()
    print("OK  编辑器（调参/旋转/美颜/人脸/消除/撤销/完成）")

    # ---- 视频剪辑 ----
    tmp = tempfile.mkdtemp()
    video_path = os.path.join(tmp, "测试视频.mp4")
    writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"),
                             25, (320, 240))
    assert writer.isOpened(), "测试视频创建失败"
    for i in range(30):
        frame = np.full((240, 320, 3), i * 8 % 255, np.uint8)
        writer.write(frame)
    writer.release()

    vw = VideoWindow(root)
    # 直接喂路径，绕过文件对话框
    cap = cv2.VideoCapture(video_path)
    assert cap.isOpened()
    vw.cap = cap
    vw.video_path = video_path
    vw.total_frames = 30
    vw.fps = 25
    vw.frame_size = (320, 240)
    vw.frame_slider.config(to=29)
    vw._show_frame(0)
    root.update()

    vw.frame_slider.set(10)
    vw._set_point("in")
    vw.frame_slider.set(20)
    vw._set_point("out")
    vw.var_brightness.set(15)

    # 把文件对话框换成直接给路径
    from tkinter import filedialog
    out_path = os.path.join(tmp, "导出结果.mp4")
    filedialog.asksaveasfilename = lambda **kw: out_path
    vw.export_video()
    assert os.path.exists(out_path) and os.path.getsize(out_path) > 0
    check = cv2.VideoCapture(out_path)
    n = 0
    while check.read()[0]:
        n += 1
    check.release()
    assert n == 11, f"入点10出点20应导出11帧，实际{n}帧"
    vw.destroy()
    root.update()
    print("OK  视频剪辑（打开/预览/入出点/调参/导出11帧）")

    root.destroy()
    print("OK  GUI全部窗口")


if __name__ == "__main__":
    test_image_ops()
    test_auth()
    test_gui()
    print()
    print("=" * 30)
    print("全部通过")
    print("=" * 30)
