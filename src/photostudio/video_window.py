# -*- coding: utf-8 -*-
"""视频剪辑窗口（VIP专属）。

能干的事：
  - 打开视频，拖进度条逐帧预览
  - 打入点/出点，截取中间一段
  - 亮度/对比度/饱和度逐帧调节（和图片编辑共用image_ops，效果所见即所得）
  - 导出成新的mp4

导出是单线程逐帧处理的，长视频会慢，进度条上能看到进度，
别看窗口卡住就狂点，那是它在干活。
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
from PIL import ImageTk

from . import image_ops as ops


class VideoWindow(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("视频剪辑（VIP）")
        self.geometry("980x640")
        self.minsize(860, 560)

        self.cap = None           # cv2.VideoCapture
        self.video_path = None
        self.total_frames = 0
        self.fps = 25
        self.frame_size = (0, 0)  # (宽, 高)
        self.frame_in = 0         # 入点（帧号）
        self.frame_out = -1       # 出点，-1表示到结尾

        self._tk_photo = None

        self._build_layout()

    # ==================== 界面 ====================

    def _build_layout(self):
        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Button(top, text="打开视频...", command=self.open_video).pack(side="left")
        self.info_label = ttk.Label(top, text="先打开一个视频文件",
                                    foreground="#666")
        self.info_label.pack(side="left", padx=12)

        middle = ttk.Frame(self)
        middle.pack(fill="both", expand=True, padx=6)

        self.canvas = tk.Canvas(middle, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        panel = ttk.Frame(middle, width=300)
        panel.pack(side="right", fill="y", padx=(8, 0))
        panel.pack_propagate(False)

        # --- 片段截取 ---
        cut = ttk.LabelFrame(panel, text=" 片段截取 ", padding=8)
        cut.pack(fill="x", pady=(0, 8))
        ttk.Button(cut, text="设为入点 [", command=lambda: self._set_point("in")
                   ).pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(cut, text="设为出点 ]", command=lambda: self._set_point("out")
                   ).pack(side="left", expand=True, fill="x", padx=2)
        self.cut_label = ttk.Label(cut, text="未截取（导出全程）",
                                   foreground="#0a7")
        self.cut_label.pack(anchor="w", pady=(6, 0))

        # --- 画面调节 ---
        adj = ttk.LabelFrame(panel, text=" 画面调节 ", padding=8)
        adj.pack(fill="x")
        self.var_brightness = tk.IntVar(value=0)
        self.var_contrast = tk.IntVar(value=100)
        self.var_saturation = tk.IntVar(value=100)

        for label, var, lo, hi in [("亮度", self.var_brightness, -100, 100),
                                   ("对比度", self.var_contrast, 50, 200),
                                   ("饱和度", self.var_saturation, 0, 200)]:
            row = ttk.Frame(adj)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=8).pack(side="left")
            ttk.Scale(row, from_=lo, to=hi, variable=var,
                      command=lambda _=None: self._debounced_preview()).pack(
                side="left", fill="x", expand=True)

        ttk.Label(adj, text="调节会应用到导出的每一帧。",
                  foreground="#666", wraplength=260).pack(anchor="w", pady=(6, 0))

        # --- 导出 ---
        exp = ttk.LabelFrame(panel, text=" 导出 ", padding=8)
        exp.pack(fill="x", pady=8)
        self.progress = ttk.Progressbar(exp, mode="determinate")
        self.progress.pack(fill="x")
        self.progress_label = ttk.Label(exp, text="等待导出", foreground="#666")
        self.progress_label.pack(anchor="w", pady=(4, 0))
        ttk.Button(exp, text="导出为新视频", command=self.export_video).pack(
            fill="x", pady=(6, 0))

        # --- 底部进度条 ---
        bottom = ttk.Frame(self, padding=(6, 0, 6, 8))
        bottom.pack(fill="x")
        ttk.Label(bottom, text="时间轴").pack(side="left")
        self.frame_slider = ttk.Scale(bottom, from_=0, to=100, orient="horizontal",
                                      command=self._on_slider)
        self.frame_slider.pack(side="left", fill="x", expand=True, padx=8)
        self.frame_label = ttk.Label(bottom, text="0", width=14)
        self.frame_label.pack(side="left")

    # ==================== 打开与预览 ====================

    def open_video(self):
        path = filedialog.askopenfilename(
            title="打开视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.flv *.wmv"),
                       ("所有文件", "*.*")])
        if not path:
            return
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            messagebox.showerror("打不开", "这个视频读不了，格式可能不支持。",
                                 parent=self)
            return

        self.cap = cap
        self.video_path = path
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 25
        self.frame_size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                           int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        self.frame_in = 0
        self.frame_out = -1

        dur = self.total_frames / self.fps
        self.info_label.config(
            text=f"{os.path.basename(path)}  {self.frame_size[0]}×{self.frame_size[1]}"
                 f"  {self.fps:.1f}帧/秒  约{dur:.0f}秒")
        self.cut_label.config(text="未截取（导出全程）")

        self.frame_slider.config(to=max(self.total_frames - 1, 0))
        self.frame_slider.set(0)
        self._show_frame(0)

    def _on_slider(self, value):
        self._show_frame(int(float(value)))

    def _debounced_preview(self):
        # 拖滑块过程中别每一下都解帧，松手后120ms再刷新
        if hasattr(self, "_job"):
            self.after_cancel(self._job)
        self._job = self.after(120, lambda: self._show_frame(
            int(float(self.frame_slider.get()))))

    def _read_frame(self, idx):
        """定位并读取第idx帧，返回BGR图或None。"""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = self.cap.read()
        return frame if ok else None

    def _current_params(self):
        return {
            "brightness": self.var_brightness.get(),
            "contrast": self.var_contrast.get(),
            "saturation": self.var_saturation.get(),
        }

    def _show_frame(self, idx, apply_params=True):
        """把第idx帧画到画布上。"""
        if self.cap is None:
            return
        frame = self._read_frame(idx)
        if frame is None:
            return
        if apply_params:
            frame = ops.apply_adjustments(frame, self._current_params())

        # 按画布大小缩放显示
        cw = max(self.canvas.winfo_width(), 100)
        ch = max(self.canvas.winfo_height(), 100)
        h, w = frame.shape[:2]
        scale = min(cw / w, ch / h, 1.0)
        disp = cv2.resize(frame, (int(w * scale), int(h * scale)))
        self._tk_photo = ImageTk.PhotoImage(ops.to_pil(disp))

        self.canvas.delete("all")
        self.canvas.create_image((cw - int(w * scale)) // 2,
                                 (ch - int(h * scale)) // 2,
                                 anchor="nw", image=self._tk_photo)
        cur_sec = idx / self.fps
        self.frame_label.config(text=f"第{idx}帧 / {cur_sec:.1f}秒")

    # ==================== 截取与导出 ====================

    def _set_point(self, which):
        if self.cap is None:
            messagebox.showinfo("提示", "先打开一个视频。", parent=self)
            return
        idx = int(float(self.frame_slider.get()))
        if which == "in":
            self.frame_in = idx
        else:
            self.frame_out = idx
        out = self.frame_out if self.frame_out >= 0 else self.total_frames - 1
        lo, hi = min(self.frame_in, out), max(self.frame_in, out)
        self.cut_label.config(
            text=f"截取：第{lo}帧 ~ 第{hi}帧"
                 f"（{(hi - lo) / self.fps:.1f}秒）")

    def export_video(self):
        if self.cap is None:
            messagebox.showinfo("提示", "先打开一个视频。", parent=self)
            return

        out_path = filedialog.asksaveasfilename(
            title="导出视频", defaultextension=".mp4",
            filetypes=[("MP4视频", "*.mp4")])
        if not out_path:
            return

        start = self.frame_in
        end = self.frame_out if self.frame_out >= 0 else self.total_frames - 1
        if start > end:
            start, end = end, start
        total = end - start + 1

        params = self._current_params()
        writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"),
                                 self.fps, self.frame_size)
        if not writer.isOpened():
            messagebox.showerror("失败", "创建输出文件失败，换个保存位置试试。",
                                 parent=self)
            return

        # 逐帧读->调->写。过程较长，每帧都让进度条走一格
        self.progress.config(maximum=total, value=0)
        done = 0
        for idx in range(start, end + 1):
            frame = self._read_frame(idx)
            if frame is None:
                break   # 视频实际帧数比标称少（损坏/截断），导出到这就停
            writer.write(ops.apply_adjustments(frame, params))
            done += 1
            self.progress.config(value=done)
            self.progress_label.config(text=f"导出中... {done}/{total} 帧")
            self.update_idletasks()   # 强制刷新界面，不然进度条不动

        writer.release()
        self.progress_label.config(text=f"导出完成，共{done}帧")
        if done:
            messagebox.showinfo("完成", f"已导出到：\n{out_path}", parent=self)
