# -*- coding: utf-8 -*-
"""图片编辑器窗口。

五个页签：基础调整 / 变换 / 美图 / 人脸 / 魔法消除。
所有真正干活的功能都调 image_ops 里的函数，这个文件只管界面和状态。

几个状态变量先说清楚，不然后面容易绕晕：
  work  当前工作图，所有"应用"过的效果都叠在它身上
  base  参数页签的基准图，拖滑块时从它出发算预览，点"应用"后追上work
  undo  撤销栈，每次修改前把旧work压进去（最多存15步，都是整图，吃内存）
  mask  魔法消除的涂抹区域，和work同宽高，涂过的地方是255
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
import numpy as np
from PIL import Image as PILImage, ImageDraw, ImageTk

from . import image_ops as ops

# 预览画布的可用尺寸，比这个大的图缩着显示
PREVIEW_MAX_W, PREVIEW_MAX_H = 780, 560


class EditorWindow(tk.Toplevel):

    def __init__(self, parent, cv_img, filename, on_save):
        super().__init__(parent)
        self.title(f"编辑图片 - {filename}")
        self.geometry("1150x680")
        self.minsize(980, 600)

        self.on_save = on_save
        self.work = cv_img.copy()
        self.base = cv_img.copy()
        self.preview_img = cv_img.copy()   # 当前画布上显示的图（可能是参数预览）
        self.undo_stack = []
        self.mask = None                   # None表示当前没在涂抹状态
        self.faces = []                    # 人脸检测结果
        self.crop_rect = None              # 变换页签里框选的裁剪区（画布坐标）

        self._build_layout()
        self._bind_canvas()
        self.refresh_preview()

    # ==================== 界面搭建 ====================

    def _build_layout(self):
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        # 左边：预览画布
        self.canvas = tk.Canvas(main, bg="#2b2b2b", highlightthickness=0,
                                cursor="crosshair")
        self.canvas.pack(side="left", fill="both", expand=True,
                         padx=(8, 4), pady=8)

        # 右边：功能面板
        panel = ttk.Frame(main, width=320)
        panel.pack(side="right", fill="y", padx=(4, 8), pady=8)
        panel.pack_propagate(False)   # 固定宽度，不被内容挤变形

        self.tabs = ttk.Notebook(panel)
        self.tabs.pack(fill="both", expand=True)
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.tab_adjust = ttk.Frame(self.tabs, padding=10)
        self.tab_transform = ttk.Frame(self.tabs, padding=10)
        self.tab_beauty = ttk.Frame(self.tabs, padding=10)
        self.tab_face = ttk.Frame(self.tabs, padding=10)
        self.tab_eraser = ttk.Frame(self.tabs, padding=10)

        self.tabs.add(self.tab_adjust, text=" 基础调整 ")
        self.tabs.add(self.tab_transform, text=" 变换 ")
        self.tabs.add(self.tab_beauty, text=" 美图 ")
        self.tabs.add(self.tab_face, text=" 人脸 ")
        self.tabs.add(self.tab_eraser, text=" 魔法消除 ")

        self._build_adjust_tab()
        self._build_transform_tab()
        self._build_beauty_tab()
        self._build_face_tab()
        self._build_eraser_tab()

        # 底部操作条
        bottom = ttk.Frame(panel, padding=(0, 10, 0, 0))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="撤销", command=self.undo).pack(side="left", padx=3)
        ttk.Button(bottom, text="另存为...", command=self.save_as).pack(
            side="left", padx=3)
        ttk.Button(bottom, text="完成", command=self._finish).pack(
            side="right", padx=3)

    def _build_adjust_tab(self):
        tab = self.tab_adjust
        ttk.Label(tab, text="拖动滑块实时预览，点「应用」生效。",
                  wraplength=280, foreground="#666").pack(anchor="w", pady=(0, 8))

        # (标签, 变量名, 最小, 最大, 默认)
        self.var_brightness = tk.IntVar(value=0)
        self.var_contrast = tk.IntVar(value=100)
        self.var_saturation = tk.IntVar(value=100)
        self.var_temperature = tk.IntVar(value=0)
        self.var_sharpen = tk.IntVar(value=0)

        rows = [
            ("亮度", self.var_brightness, -100, 100),
            ("对比度", self.var_contrast, 50, 200),
            ("饱和度", self.var_saturation, 0, 200),
            ("色温（冷→暖）", self.var_temperature, -50, 50),
            ("锐化", self.var_sharpen, 0, 100),
        ]
        for label, var, lo, hi in rows:
            row = ttk.Frame(tab)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, width=12).pack(side="left")
            # 值变化的瞬间不重算（大图会卡），松开鼠标才刷新预览
            s = ttk.Scale(row, from_=lo, to=hi, variable=var,
                          command=lambda _=None, v=var: self._after_release(v))
            s.pack(side="left", fill="x", expand=True)

        btns = ttk.Frame(tab)
        btns.pack(fill="x", pady=(14, 0))
        ttk.Button(btns, text="应用", command=self._apply_adjustments).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(btns, text="重置参数", command=self._reset_adjustments).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

    def _build_transform_tab(self):
        tab = self.tab_transform
        ttk.Label(tab, text="旋转和翻转点了立刻生效。",
                  wraplength=280, foreground="#666").pack(anchor="w", pady=(0, 8))

        grid = ttk.Frame(tab)
        grid.pack(fill="x")
        for i, (text, cmd) in enumerate([
                ("左转90°", lambda: self._transform(lambda im: ops.rotate(im, 3))),
                ("右转90°", lambda: self._transform(lambda im: ops.rotate(im, 1))),
                ("水平翻转", lambda: self._transform(lambda im: ops.flip(im, 1))),
                ("垂直翻转", lambda: self._transform(lambda im: ops.flip(im, 0)))]):
            ttk.Button(grid, text=text, command=cmd).grid(
                row=i // 2, column=i % 2, padx=4, pady=4, sticky="nsew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        ttk.Separator(tab).pack(fill="x", pady=12)
        ttk.Label(tab, text="裁剪：切到本页签后在图上按住左键框选区域，"
                            "框好点下面的按钮。",
                  wraplength=280, foreground="#666").pack(anchor="w")
        ttk.Button(tab, text="裁剪到框选区域", command=self._apply_crop).pack(
            fill="x", pady=(10, 0))

    def _build_beauty_tab(self):
        tab = self.tab_beauty
        ttk.Label(tab, text="磨皮用双边滤波，糊皮肤不糊轮廓。",
                  wraplength=280, foreground="#666").pack(anchor="w", pady=(0, 8))

        self.var_smooth = tk.IntVar(value=50)
        self.var_whiten = tk.IntVar(value=30)

        for label, var in [("磨皮强度", self.var_smooth), ("美白程度", self.var_whiten)]:
            row = ttk.Frame(tab)
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, width=12).pack(side="left")
            ttk.Scale(row, from_=0, to=100, variable=var).pack(
                side="left", fill="x", expand=True)

        ttk.Button(tab, text="应用磨皮",
                   command=lambda: self._apply_beauty_op(
                       lambda im: ops.smooth_skin(im, self.var_smooth.get()))
                   ).pack(fill="x", pady=(10, 2))
        ttk.Button(tab, text="应用美白",
                   command=lambda: self._apply_beauty_op(
                       lambda im: ops.whiten(im, self.var_whiten.get() / 100.0))
                   ).pack(fill="x", pady=2)

        ttk.Separator(tab).pack(fill="x", pady=12)
        ttk.Button(tab, text="一键美颜", command=self._auto_beauty).pack(
            fill="x", pady=4)
        ttk.Label(tab, text="（磨皮+美白+找回一点锐度，适合懒人）",
                  foreground="#666").pack(anchor="w")

    def _build_face_tab(self):
        tab = self.tab_face
        ttk.Label(tab, text="检测图中的人脸并框出来，可以只给人脸做美颜，"
                            "背景不动。",
                  wraplength=280, foreground="#666").pack(anchor="w", pady=(0, 8))
        ttk.Button(tab, text="检测人脸", command=self._detect_faces).pack(
            fill="x", pady=2)
        ttk.Button(tab, text="给人脸美颜", command=self._beautify_faces).pack(
            fill="x", pady=2)
        self.face_info = ttk.Label(tab, text="还没检测过", foreground="#0a7")
        self.face_info.pack(anchor="w", pady=8)

    def _build_eraser_tab(self):
        tab = self.tab_eraser
        ttk.Label(tab, text="用笔刷涂满想消除的东西（路人、杂物...），"
                            "点「执行消除」让AI把它抹掉。\n"
                            "小面积效果最好，一次别涂太大块。",
                  wraplength=280, foreground="#666", justify="left").pack(
            anchor="w", pady=(0, 8))

        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="笔刷大小", width=12).pack(side="left")
        self.var_brush = tk.IntVar(value=30)
        ttk.Scale(row, from_=10, to=80, variable=self.var_brush).pack(
            side="left", fill="x", expand=True)

        ttk.Button(tab, text="清除涂抹", command=self._clear_mask).pack(
            fill="x", pady=(12, 2))
        ttk.Button(tab, text="执行消除", command=self._do_inpaint).pack(
            fill="x", pady=2)

    # ==================== 画布与坐标换算 ====================

    def _bind_canvas(self):
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        # 画布尺寸变化时重新适配预览
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.after_idle(self.refresh_preview))

    def _current_tab(self):
        widget = self.tabs.select()
        for tab in (self.tab_transform, self.tab_eraser):
            if widget == str(tab):
                return tab
        return None

    def _on_tab_changed(self, _event):
        # 切走变换/消除页签时清掉临时状态，免得残留误导人
        if self._current_tab() is not self.tab_transform:
            self.crop_rect = None
        if self._current_tab() is not self.tab_eraser:
            pass   # mask留着，切回来还能接着涂
        self.refresh_preview()

    def _canvas_to_image(self, cx, cy):
        """画布坐标换算成原图像素坐标。"""
        x = (cx - self.disp_off_x) / self.disp_scale
        y = (cy - self.disp_off_y) / self.disp_scale
        return int(x), int(y)

    def _on_press(self, event):
        self._press_xy = (event.x, event.y)
        if self._current_tab() is self.tab_eraser:
            if self.mask is None:
                self.mask = np.zeros(self.work.shape[:2], np.uint8)
            self._paint(event.x, event.y)

    def _on_drag(self, event):
        tab = self._current_tab()
        if tab is self.tab_eraser:
            # 两点之间补一笔，快速拖动才不会断成虚线
            x0, y0 = self._press_xy
            steps = max(abs(event.x - x0), abs(event.y - y0)) // 4 + 1
            for i in range(steps + 1):
                t = i / max(steps, 1)
                self._paint(int(x0 + (event.x - x0) * t),
                            int(y0 + (event.y - y0) * t))
            self._press_xy = (event.x, event.y)
        elif tab is self.tab_transform:
            self.crop_rect = (self._press_xy, (event.x, event.y))
            self.refresh_preview()

    def _on_release(self, event):
        if self._current_tab() is self.tab_transform and self.crop_rect:
            # 框选结束，规整成左上-右下的顺序
            (x0, y0), (x1, y1) = self.crop_rect
            self.crop_rect = (min(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1))
            self.refresh_preview()

    def _paint(self, cx, cy):
        """在mask上以(cx,cy)画布坐标为圆心涂一笔。"""
        ix, iy = self._canvas_to_image(cx, cy)
        r = int(self.var_brush.get() / 2 / self.disp_scale)
        cv2.circle(self.mask, (ix, iy), max(2, r), 255, -1)
        self.refresh_preview()

    # ==================== 预览渲染 ====================

    def refresh_preview(self):
        """把preview_img缩放后画到画布上，再叠加各页签的临时标记。"""
        img = self.preview_img
        h, w = img.shape[:2]

        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        # 预览画布区域内适配
        self.disp_scale = min(PREVIEW_MAX_W / w, PREVIEW_MAX_H / h,
                              cw / w, ch / h, 1.0)
        dw, dh = int(w * self.disp_scale), int(h * self.disp_scale)
        self.disp_off_x = (cw - dw) // 2
        self.disp_off_y = (ch - dh) // 2

        pil = ops.to_pil(img).resize((dw, dh))
        draw = ImageDraw.Draw(pil, "RGBA")

        # 叠加：人脸框（绿色）
        if self.faces:
            for (x, y, fw, fh) in self.faces:
                draw.rectangle(
                    [x * self.disp_scale, y * self.disp_scale,
                     (x + fw) * self.disp_scale, (y + fh) * self.disp_scale],
                    outline="#00e676", width=3)

        # 叠加：魔法消除的涂抹区域（半透明红）
        if self.mask is not None and self.mask.any():
            m = (self.mask > 0)
            overlay = np.zeros((h, w, 4), np.uint8)
            overlay[m] = (255, 40, 40, 110)
            ov = PILImage.fromarray(overlay, "RGBA").resize((dw, dh))
            pil = pil.convert("RGBA")
            pil.alpha_composite(ov)
            draw = ImageDraw.Draw(pil, "RGBA")

        # 叠加：裁剪框（黄色虚线感——tk没虚线，画四角加边框凑合看）
        if self.crop_rect:
            (x0, y0), (x1, y1) = self.crop_rect
            draw.rectangle([x0, y0, x1, y1], outline="#ffd54f", width=2)

        self._tk_photo = ImageTk.PhotoImage(pil)
        self.canvas.delete("all")
        self.canvas.create_image(self.disp_off_x, self.disp_off_y,
                                 anchor="nw", image=self._tk_photo)

    # ==================== 各功能的动作 ====================

    def _push_undo(self):
        self.undo_stack.append(self.work)
        if len(self.undo_stack) > 15:
            self.undo_stack.pop(0)   # 最多15步，都是整图，多了内存遭不住

    def _commit(self, new_img):
        """把一张新图确认为当前work，同步base并刷新预览。"""
        self._push_undo()
        self.work = new_img
        self.base = new_img.copy()
        self.preview_img = new_img
        self.faces = []          # 图变了，旧的人脸框坐标已经作废
        self.crop_rect = None
        self.refresh_preview()

    def _after_release(self, var):
        # Scale的command是连续触发的，这里只在松手那一刻重算预览。
        # 用after(120)做防抖：120ms内的连续触发只留最后一次
        if hasattr(self, "_adjust_job"):
            self.after_cancel(self._adjust_job)
        self._adjust_job = self.after(120, self._preview_adjustments)

    def _preview_adjustments(self):
        params = {
            "brightness": self.var_brightness.get(),
            "contrast": self.var_contrast.get(),
            "saturation": self.var_saturation.get(),
            "temperature": self.var_temperature.get(),
            "sharpen": self.var_sharpen.get(),
        }
        self.preview_img = ops.apply_adjustments(self.base, params)
        self.refresh_preview()

    def _apply_adjustments(self):
        self._preview_adjustments()
        self._commit(self.preview_img)
        self._reset_adjustments()

    def _reset_adjustments(self):
        for var, default in [(self.var_brightness, 0), (self.var_contrast, 100),
                             (self.var_saturation, 100), (self.var_temperature, 0),
                             (self.var_sharpen, 0)]:
            var.set(default)
        self.preview_img = self.work
        self.refresh_preview()

    def _transform(self, fn):
        self._commit(fn(self.work))

    def _apply_crop(self):
        if not self.crop_rect:
            messagebox.showinfo("提示", "先在图上框选一块区域。", parent=self)
            return
        (x0, y0), (x1, y1) = self.crop_rect
        ix0, iy0 = self._canvas_to_image(x0, y0)
        ix1, iy1 = self._canvas_to_image(x1, y1)
        result = ops.crop(self.work, ix0, iy0, ix1, iy1)
        if result is None:
            messagebox.showwarning("提示", "框选的区域太小了，重新框大一点。",
                                   parent=self)
            return
        self._commit(result)

    def _apply_beauty_op(self, fn):
        self._commit(fn(self.work))

    def _auto_beauty(self):
        self._commit(ops.auto_beauty(self.work))

    def _detect_faces(self):
        self.faces = ops.detect_faces(self.work)
        n = len(self.faces)
        self.face_info.config(
            text=f"检出 {n} 张人脸" if n else "没检出人脸，试试正脸、光线好点的照片")
        self.refresh_preview()

    def _beautify_faces(self):
        if not self.faces:
            messagebox.showinfo("提示", "先点「检测人脸」。", parent=self)
            return
        self._commit(ops.beauty_on_faces(self.work, self.faces))

    def _clear_mask(self):
        self.mask = None
        self.refresh_preview()

    def _do_inpaint(self):
        if self.mask is None or not self.mask.any():
            messagebox.showinfo("提示", "先用笔刷涂一块区域再消除。", parent=self)
            return
        self._commit(ops.inpaint(self.work, self.mask))
        self.mask = None

    # ==================== 撤销 / 保存 / 完成 ====================

    def undo(self):
        if not self.undo_stack:
            messagebox.showinfo("提示", "没有可以撤销的操作了。", parent=self)
            return
        self.work = self.undo_stack.pop()
        self.base = self.work.copy()
        self.preview_img = self.work
        self.faces = []
        self.mask = None
        self.crop_rect = None
        self._reset_adjustments()

    def save_as(self):
        path = filedialog.asksaveasfilename(
            title="另存为", defaultextension=".jpg",
            filetypes=[("JPEG图片", "*.jpg"), ("PNG图片", "*.png")])
        if not path:
            return
        if ops.save_image(self.work, path):
            messagebox.showinfo("成功", f"已保存到：\n{path}", parent=self)
        else:
            messagebox.showerror("失败", "保存出错了，看下路径和后缀名。", parent=self)

    def _finish(self):
        self.on_save(self.work)
        self.destroy()
