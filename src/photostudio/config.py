# -*- coding: utf-8 -*-
"""全局配置：版本信息、路径解析。

路径这块多说两句，因为打包和不打包时目录结构完全不一样：
  - 直接跑源码时，项目根目录就是 E:\\PhotoStudio，数据放项目根的 data/ 里
  - PyInstaller打包后，代码被解压到临时目录，只有exe旁边是稳定的
所以所有路径都从下面这几个函数里拿，别在别的地方自己拼路径，
不然以后打包必然踩坑。
"""
import sys
from pathlib import Path

# 版本与作者信息，改这里全局生效
VERSION = "1.0"
APP_NAME = "光影工坊"
APP_NAME_EN = "PhotoStudio"
AUTHOR = "shurou116"
EMAIL = "2693845540@qq.com"

# 以后接服务器的时候，把这里填上你的API地址，
# 然后把 auth.py 里的 UserStore 换成走网络请求的实现就行。
API_BASE = ""


def is_frozen() -> bool:
    """判断当前是不是在PyInstaller打包的exe里跑。"""
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    """拿到程序的可写根目录（放用户数据用）。

    源码运行：src/photostudio/config.py 往上三级是项目根
    exe运行：exe自己所在的目录
    """
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """数据目录，不存在就顺手建一个。"""
    d = app_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def users_csv() -> Path:
    """用户账号表的位置。"""
    return data_dir() / "users.csv"


def resource_path(rel: str) -> Path:
    """静态资源路径（目前就一个人脸检测模型 + 操作手册）。

    rel 是相对 src/ 的路径，比如 "resources/haarcascade_frontalface_default.xml"。
    打包时这些文件会被 --add-data 塞进exe的临时解压目录 _MEIPASS。
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", ".")) / rel
    return Path(__file__).resolve().parents[1] / rel


def manual_path():
    """找操作手册，找到哪个算哪个；两头都找不到返回None。"""
    candidates = [
        app_root() / "docs" / "操作手册.txt",      # 源码运行 / 手册拷在exe旁边
        resource_path("操作手册.txt"),               # 打包时 --add-data 进去的
    ]
    for p in candidates:
        if p.exists():
            return p
    return None
