# -*- coding: utf-8 -*-
"""图像算法层：所有对像素的加工都在这个文件里，纯函数，不碰任何界面代码。

为什么单独拆一层：
  1. 界面代码和算法代码分开，改界面不会误伤算法，反过来也一样
  2. 想加新效果，就在这里写一个 def xxx(img, 参数) -> 新图，
     再到界面挂个滑块调用它，两步完事
  3. 以后如果做网页版或者服务端处理，这些函数原封不动搬过去就能用

约定：
  - 输入输出一律是OpenCV的BGR格式 ndarray，uint8
  - 函数不修改传入的图，返回处理后的新数组
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image as PILImage, ImageOps

from .config import resource_path

# 支持的图片后缀，打开文件夹时按这个过滤
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tif", ".tiff"}


# ==================== 读文件 / 存文件 ====================

def load_image(path):
    """读图片，返回BGR ndarray。

    不用cv2.imread是因为它在Windows上读不了中文路径，
    这里走PIL再转BGR，顺便把手机照片的EXIF旋转方向也摆正了。
    """
    with PILImage.open(path) as im:
        im = ImageOps.exif_transpose(im)   # 按EXIF信息转正，竖拍照片不会躺倒
        rgb = im.convert("RGB")
    return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)


def save_image(img, path, quality=95):
    """存图片。同样因为中文路径问题，先编码到内存再写文件。"""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".png":
        ok, buf = cv2.imencode(".png", img)
    else:
        # jpg/jpeg/webp都走jpeg编码，不认识的后缀也按jpg存，省得报错
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if ok:
        buf.tofile(str(path))   # tofile认中文路径，imwrite不认
    return ok


def to_pil(img):
    """BGR ndarray -> PIL Image，给tkinter显示用。"""
    return PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


# ==================== 基础参数调节 ====================

def adjust_brightness(img, delta):
    """亮度，delta范围-100~100，往每个像素上加一个固定值。"""
    return np.clip(img.astype(np.int16) + delta * 255 // 100,
                   0, 255).astype(np.uint8)


def adjust_contrast(img, factor):
    """对比度，factor 0~2，1是原图。以128的中灰为轴心往外拉/往里压。"""
    return np.clip((img.astype(np.float32) - 128.0) * factor + 128.0,
                   0, 255).astype(np.uint8)


def adjust_saturation(img, factor):
    """饱和度，factor 0~2，1是原图。转到HSV后只动S通道。"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1].astype(np.float32) * factor,
                          0, 255).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def adjust_temperature(img, delta):
    """色温，delta -50~50。正数偏暖（红多蓝少），负数偏冷（蓝多红少）。"""
    out = img.astype(np.int16)
    out[..., 0] = np.clip(out[..., 0] - delta, 0, 255)   # B通道
    out[..., 2] = np.clip(out[..., 2] + delta, 0, 255)   # R通道
    return out.astype(np.uint8)


def sharpen(img, amount):
    """锐化，amount 0~2。钝化掩模（USM）做法：原图和模糊图加权相减。"""
    if amount <= 0:
        return img.copy()
    blur = cv2.GaussianBlur(img, (0, 0), 3)
    return cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)


def apply_adjustments(img, params):
    """把一组参数一次性套到图上。编辑器和视频导出共用这一份逻辑，
    保证"预览看到啥，导出就是啥"。

    params字段（都可以缺省）：brightness/contrast/saturation/temperature/sharpen
    """
    out = img
    if params.get("brightness"):
        out = adjust_brightness(out, params["brightness"])
    if params.get("contrast", 100) != 100:
        out = adjust_contrast(out, params["contrast"] / 100.0)
    if params.get("saturation", 100) != 100:
        out = adjust_saturation(out, params["saturation"] / 100.0)
    if params.get("temperature"):
        out = adjust_temperature(out, params["temperature"])
    if params.get("sharpen"):
        out = sharpen(out, params["sharpen"] / 50.0)
    return out


# ==================== 几何变换 ====================

def rotate(img, quarter):
    """旋转，quarter单位是90°：1右转90，2转180，3左转90。"""
    quarter %= 4
    if quarter == 0:
        return img.copy()
    code = {1: cv2.ROTATE_90_CLOCKWISE,
            2: cv2.ROTATE_180,
            3: cv2.ROTATE_90_COUNTERCLOCKWISE}[quarter]
    return cv2.rotate(img, code)


def flip(img, code):
    """翻转：code 1是水平镜像，0是垂直镜像。"""
    return cv2.flip(img, code)


def crop(img, x0, y0, x1, y1):
    """裁剪，坐标是像素，自动容忍边界。"""
    h, w = img.shape[:2]
    x0, x1 = max(0, min(x0, x1)), min(w, max(x0, x1))
    y0, y1 = max(0, min(y0, y1)), min(h, max(y0, y1))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None   # 框选区域太小，当成没选
    return img[y0:y1, x0:x1].copy()


# ==================== 美图 ====================

def smooth_skin(img, strength):
    """磨皮，strength 0~100。双边滤波——比高斯模糊强在能保住边缘，
    皮肤糊掉的同时五官轮廓还在，这是磨皮的经典套路。"""
    if strength <= 0:
        return img.copy()
    d = 5 + int(strength / 100 * 20)      # 滤波邻域直径，强度越大越糊
    d = d if d % 2 == 1 else d + 1
    return cv2.bilateralFilter(img, d, d * 2, d * 2)


def whiten(img, factor):
    """美白，factor 0~1。把HSV的V通道往255方向抬，只抬一半幅度，
    抬满会过曝白成一片。"""
    if factor <= 0:
        return img.copy()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    v = hsv[..., 2].astype(np.float32)
    hsv[..., 2] = np.clip(v + (255 - v) * factor * 0.5, 0, 255).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def auto_beauty(img):
    """一键美颜：磨皮 + 美白 + 轻微锐化找回一点质感。"""
    out = smooth_skin(img, 60)
    out = whiten(out, 0.35)
    return sharpen(out, 0.3)


# ==================== 人脸检测 ====================

_face_detector = None   # 模型加载一次就够了，缓存起来重复用


def _get_face_detector():
    """加载YuNet人脸检测模型（OpenCV官方动物园出品，232KB的ONNX）。

    说明一下为什么不用教程里常见的Haar级联：OpenCV 5.0已经把
    CascadeClassifier整个移除了，YuNet是官方指定的替代品，
    检测精度更高、支持侧脸和遮挡，CPU上速度也够快。
    """
    global _face_detector
    if _face_detector is None:
        model = str(resource_path("resources/face_detection_yunet_2023mar.onnx"))
        _face_detector = cv2.FaceDetectorYN_create(model, "", (320, 320),
                                                   score_threshold=0.6)
        if _face_detector is None:
            raise RuntimeError("人脸模型加载失败，检查resources目录: " + model)
    return _face_detector


def detect_faces(img):
    """人脸检测，返回[(x, y, w, h), ...]。

    策略：大图先缩到长边800以内再检测（速度快一个量级），
    检出的框再按比例换算回原图坐标。
    """
    h, w = img.shape[:2]
    scale = 1.0
    if max(h, w) > 800:
        scale = 800.0 / max(h, w)
        small = cv2.resize(img, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)
    else:
        small = img

    det = _get_face_detector()
    # YuNet要求每次检测前声明输入图的尺寸
    det.setInputSize((small.shape[1], small.shape[0]))
    _, faces = det.detect(small)

    result = []
    if faces is not None:
        for f in faces:
            # 每行15个数：x,y,w,h + 5个关键点坐标(眼鼻嘴) + 置信度
            x, y, fw, fh = f[0], f[1], f[2], f[3]
            result.append((int(x / scale), int(y / scale),
                           int(fw / scale), int(fh / scale)))
    return result


def beauty_on_faces(img, faces):
    """只对检出的人脸区域做美颜，背景一点不动。"""
    out = img.copy()
    h, w = img.shape[:2]
    for (x, y, fw, fh) in faces:
        pad = int(fh * 0.2)   # 人脸框往外扩20%，额头下巴别漏掉
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + fw + pad), min(h, y + fh + pad)
        out[y0:y1, x0:x1] = auto_beauty(img[y0:y1, x0:x1])
    return out


# ==================== 魔法消除 ====================

def inpaint(img, mask, radius=5):
    """魔法消除的核心：把mask标白的区域按周围像素"脑补"掉。

    mask要求和img同宽高，8位单通道，涂过的位置是255，其余是0。
    TELEA算法速度和效果比较均衡，日常够用。
    """
    return cv2.inpaint(img, mask, radius, cv2.INPAINT_TELEA)
