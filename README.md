# FY4B Wallpaper

自动下载 **风云四号 B 星 (FY-4B)** 静止轨道卫星云图并设置为桌面壁纸。

## 功能

- 定时下载 FY-4B 全圆盘云图（每小时的 10/25/40/55 分）
- 自动设置为桌面壁纸（Linux：Cinnamon / GNOME / KDE / Xfce / MATE；Windows 10/11）
- 时间轴缓存：断网或下载失败时自动回退到本地最新壁纸
- 临时下载放在系统临时目录，用完即删，启动时清理历史遗留文件，不会长期占用磁盘
- 单实例锁，避免重复运行
- 系统唤醒检测，挂起恢复后自动更新
- 跨平台同一份代码：Linux 走 XDG 目录与 deb 自启，Windows 走 `%LOCALAPPDATA%` 与注册表自启

## 数据存放位置

**Linux** 全部遵循 XDG 规范，不占用用户图片目录（可用 `XDG_DATA_HOME` / `XDG_CACHE_HOME` 覆盖）：

| 内容 | 路径 | 说明 |
| --- | --- | --- |
| 壁纸时间轴 | `~/.local/share/fy4b/timeline/` | 每小时 4 个槽位（`HH-10/25/40/55.jpg`），每天覆盖写入，占用有上限 |
| 临时下载 | `/tmp/fy4b/` | 拷贝进时间轴后立即删除；即使进程崩溃，关机后系统也会回收 `/tmp` |
| 日志 | `~/.cache/fy4b/fy4b.log` | |
| 单实例锁 | `~/.cache/fy4b/app.lock` | |

**Windows** 统一放在 `%LOCALAPPDATA%\fy4b`（可用 `LOCALAPPDATA` 覆盖）：

| 内容 | 路径 |
| --- | --- |
| 壁纸时间轴 | `%LOCALAPPDATA%\fy4b\timeline\` |
| 临时下载 | `%TEMP%\fy4b\` |
| 日志 | `%LOCALAPPDATA%\fy4b\cache\fy4b.log` |
| 单实例锁 | `%LOCALAPPDATA%\fy4b\cache\app.lock` |
| 开机自启 | 注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`，值名 `fy4b-wp` |

从旧版本（`~/Pictures/FY4B/timeline/`）升级时，首次启动会自动把已有壁纸迁移到新位置，并清理旧版本遗留在 `~/.cache/fy4b/` 下的原始下载文件。

## 安装

### 通过 deb 包安装（推荐）

从 [Releases](https://github.com/915P/FY4B/releases) 下载最新 `.deb` 包：

```bash
sudo dpkg -i fy4b-wp_*.deb
sudo apt install -f   # 安装依赖
```

安装后服务会自动启动，每 15 分钟更新壁纸。

### 手动运行

```bash
git clone https://github.com/915P/FY4B.git
cd FY4B
pip install -r requirements.txt
python3 FY4B.py
```

### Windows

需要 Python 3.10+：

```powershell
git clone https://github.com/915P/FY4B.git
cd FY4B
pip install -r requirements.txt
python FY4B.py
```

- 首次以正常模式启动时会自动把 `fy4b-wp` 写入 `HKCU\...\CurrentVersion\Run` 实现开机自启
- 壁纸样式为 Fit（保持比例缩放，等同 Linux 的 `scaled`），需要改样式可调 `FY4B.py` 里的 `WINDOWS_WALLPAPER_STYLE`（`10` = Fill 铺满裁剪）
- 也可以打包成单文件 exe：`build.bat`（产物 `dist\fy4b-wp.exe`），或手动执行 `pyinstaller --onefile --noconsole --name fy4b-wp FY4B.py`

### 命令行参数

| 参数 | 作用 |
| --- | --- |
| `--once` | 只执行一次更新后退出（用于测试，不注册自启、不起调度器） |
| `--remove-autostart` | 移除开机自启项后退出（仅 Windows） |
| `-h` / `--help` | 显示帮助 |

## 构建

### deb 包（Linux）

```bash
bash build.sh
```

产物在 `dist/` 目录下。

### exe（Windows）

```powershell
.\build.bat
```

产物为 `dist\fy4b-wp.exe`（无控制台窗口，日志见 `%LOCALAPPDATA%\fy4b\cache\fy4b.log`）。

## 技术原理

- 数据源：国家卫星气象中心 FY-4B L1 全圆盘云图
- 使用 `APScheduler` 定时调度
- 使用 `Pillow` 处理大尺寸卫星云图
- 使用 `filelock` 保证单实例运行
- Linux 通过 `gsettings` / `xfconf-query` 等桌面命令设置壁纸；Windows 通过 `SystemParametersInfoW` + 注册表样式值设置壁纸

## 许可证

MIT License，见 [LICENSE](LICENSE)。