# 光影工坊 PhotoStudio

本地看图 + 图片编辑 + VIP 视频剪辑软件。

- 版本：1.0
- 作者：shurou116
- 邮箱：2693845540@qq.com

## 运行

```bash
# 依赖：Python 3.10+，opencv-python、numpy、Pillow（tkinter是Python自带的）
python src/main.py
```

跑一遍功能测试（不开消息循环，几十秒跑完）：

```bash
python tests/smoke_test.py
```

## 目录结构

```
PhotoStudio/
├── src/                    # 源代码（和打包产物分开）
│   ├── main.py             # 程序入口
│   ├── photostudio/
│   │   ├── config.py       # 版本信息、路径解析
│   │   ├── auth.py         # 用户系统（CSV存储）
│   │   ├── login_window.py # 登录/注册窗口
│   │   ├── vip_dialog.py   # VIP充值窗口
│   │   ├── main_window.py  # 看图主界面
│   │   ├── editor_window.py# 图片编辑器
│   │   ├── video_window.py # VIP视频剪辑
│   │   └── image_ops.py    # 图像算法层（纯函数，无界面）
│   └── resources/          # 人脸检测模型等静态资源
├── dist/                   # PyInstaller打包产物（不进git）
├── data/                   # 运行时数据：users.csv（不进git）
├── docs/操作手册.txt        # 用户手册
└── tests/smoke_test.py     # 冒烟测试
```

## 怎么加新功能

这个项目分层很简单，就三层：

1. **算法**：在 `src/photostudio/image_ops.py` 里加一个纯函数，
   输入 BGR ndarray 输出新 ndarray，不碰任何界面代码。
2. **界面**：在对应的窗口文件里加控件（滑块/按钮），
   调用上面那个函数。编辑器的每个页签就是一个 Frame，
   照着"美图"页签抄一个最快。
3. **说明**：在 `docs/操作手册.txt` 里补一段用法。

## 以后怎么接服务器

用户数据全走 `auth.py` 的 `UserStore`（register / login / recharge_vip
三个方法）。接服务器时写一个 `ServerUserStore` 实现同样三个方法，
在 `src/main.py` 里把 `UserStore()` 换成它，界面代码零改动。
API 地址预留位置在 `config.py` 的 `API_BASE`。

图片算法层（image_ops.py）本身不依赖界面，以后做网页版、
服务端批量处理可以直接复用。

## 打包

```bash
pip install pyinstaller
pyinstaller --noconsole --name PhotoStudio --distpath dist --workpath build \
    --add-data "src/resources;resources" \
    --add-data "docs/操作手册.txt;." \
    src/main.py
```

产物在 `dist/PhotoStudio/PhotoStudio.exe`，整个文件夹拷走就能用。

## 已知限制

- 人脸检测用 YuNet，侧脸/暗光/小脸会漏检（正常水平）
- 魔法消除对大面积区域效果一般，小面积多涂几次更好
- 视频导出是单线程逐帧处理，长视频慢，看进度条别急
- 撤销栈最多15步且存整图，超大图片编辑时内存吃得比较多
