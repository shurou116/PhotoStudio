# -*- coding: utf-8 -*-
"""用户系统：注册、登录、VIP状态，数据存本地CSV。

设计说明（想加功能的先看这里）：
  所有用户读写都走 UserStore 这一个类，界面层只跟它打交道。
  现在是本地CSV，以后要接服务器，写一个 ServerUserStore 实现同样的
  register / login / recharge_vip 三个方法，替换掉实例化的那行就完事，
  界面代码一行都不用动。

CSV格式（带表头，utf-8-sig编码，Excel能直接打开看）：
  username, password, salt, is_vip, created_at
  密码存的是加盐哈希，不是明文。本地演示版用sha256够了，
  真要联网请换成bcrypt这种慢哈希，别把这个直接搬上线。
"""
import csv
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime

from .config import users_csv


@dataclass
class User:
    """登录成功后拿到手的用户信息，界面层只看这个。"""
    username: str
    is_vip: bool
    created_at: str


class UserStore:
    FIELDS = ["username", "password", "salt", "is_vip", "created_at"]

    def __init__(self, path=None):
        # path参数是给测试用的，平时不传就走config里的默认位置
        self.path = path or users_csv()
        self.users = {}          # username -> 原始行数据dict
        self._load()

    # ---------- 文件读写 ----------

    def _load(self):
        if not self.path.exists():
            return
        with open(self.path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                self.users[row["username"]] = dict(row)

    def _save(self):
        with open(self.path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDS)
            writer.writeheader()
            writer.writerows(self.users.values())

    # ---------- 密码处理 ----------

    @staticmethod
    def _hash(password: str, salt: str) -> str:
        # 盐拼在密码前面一起哈希。同一个人每次注册的盐都不一样，
        # 这样就算两个人密码一样，CSV里存的哈希也对不上号
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    # ---------- 对外的三个核心方法 ----------

    def register(self, username: str, password: str):
        """注册。返回 (是否成功, 提示消息)。"""
        username = username.strip()
        if not username or not password:
            return False, "账号和密码都不能为空"
        if username in self.users:
            return False, "这个账号已经被注册过了"
        if len(password) < 3:
            return False, "密码至少要3位"
        if "," in username:
            # CSV按逗号分列，账号里带逗号会把表搞乱，直接禁掉
            return False, "账号里不能有英文逗号"

        salt = secrets.token_hex(8)
        self.users[username] = {
            "username": username,
            "password": self._hash(password, salt),
            "salt": salt,
            "is_vip": "0",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._save()
        return True, "注册成功，已自动登录"

    def login(self, username: str, password: str):
        """登录。成功返回User，失败返回None，两边都带提示消息。"""
        row = self.users.get(username.strip())
        if row is None or row["password"] != self._hash(password, row["salt"]):
            # 账号不存在和密码错误给同一句话，不给撞库的人提示
            return None, "账号或密码不正确"
        user = User(row["username"], row["is_vip"] == "1", row["created_at"])
        return user, f"欢迎回来，{user.username}"

    def recharge_vip(self, username: str) -> bool:
        """给指定账号开通VIP。充值入口点一下就免费开通，走的就是这里。"""
        row = self.users.get(username)
        if row is None:
            return False
        row["is_vip"] = "1"
        self._save()
        return True
