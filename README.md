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

### Linux：deb 包（推荐）

从 [Releases](https://github.com/915P/FY4B/releases) 下载 `fy4b-wp_<版本>_amd64.deb`：

```bash
sudo dpkg -i fy4b-wp_*.deb
sudo apt install -f   # 补齐依赖
```

安装后随桌面会话自动启动（`/etc/xdg/autostart`），每小时的 10/25/40/55 分更新壁纸。

卸载：`sudo dpkg -r fy4b-wp`；如需彻底清理，再删除 `~/.local/share/fy4b` 与 `~/.cache/fy4b`。

### Windows：安装程序（推荐）

从 [Releases](https://github.com/915P/FY4B/releases) 下载 `fy4b-wp-setup.exe`，双击运行，一路「下一步」即可：

- 图形安装向导（简体中文），默认装到 `%LOCALAPPDATA%\Programs\fy4b`，**按用户安装、不需要管理员权限**
- **不创建任何快捷方式**（桌面、开始菜单都没有），也没有勾选页
- 装完立即在后台静默启动，开机自启自动注册（无选项）

安装后：

- 程序在后台安静运行，每小时的 10/25/40/55 分自动换图，全程无窗口
- 出现在「设置 → 应用 → 已安装的应用」里，可由系统直接卸载
- 日志见 `%LOCALAPPDATA%\fy4b\cache\fy4b.log`
- 想手动启动：直接运行 `%LOCALAPPDATA%\Programs\fy4b\fy4b-wp.exe`（单实例，重复运行会自动退出）

卸载：`设置 → 应用 → FY4B 云图壁纸 → 卸载`（或安装目录下的 `unins000.exe`，**程序运行中也能卸**）。
卸载会**彻底清理、不留残余**，依次执行：

1. 结束进程 → 移除开机自启
2. 删除安装目录、数据目录 `%LOCALAPPDATA%\fy4b`（壁纸时间轴与日志，跑满一天约 0.5~1.4 GB）、临时下载目录 `%TEMP%\fy4b`
3. 若当前壁纸还是本程序设置的那张，自动换回系统默认壁纸并还原壁纸样式（中途换过壁纸则不动你的桌面设置）

静默安装/卸载（供脚本使用）：

```powershell
.\fy4b-wp-setup.exe /VERYSILENT /NORESTART                                    # 安装
& "$env:LOCALAPPDATA\Programs\fy4b\unins000.exe" /VERYSILENT /NORESTART        # 卸载
```

> exe 未做代码签名，SmartScreen 或部分杀毒软件可能拦截：点「更多信息」→「仍要运行」即可。

### Windows：单文件 exe（免安装）

只想解压即用也可以，直接下载 `fy4b-wp.exe`：

1. **先放到固定位置再运行**（例如 `C:\fy4b\fy4b-wp.exe`）。首次运行会把当时的完整路径写入注册表自启，之后再移动 exe 会让开机自启失效（重新运行一次即可覆盖为新路径）
2. 双击运行：立即下载云图并设置为壁纸，同时自动写入 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`（值名 `fy4b-wp`）实现开机自启

停止运行：任务管理器结束 `fy4b-wp` 进程，或 `taskkill /IM fy4b-wp.exe /F`。

卸载（免安装版）：

1. `fy4b-wp.exe --remove-autostart` —— 移除开机自启项（**程序运行中也可直接执行**）
2. 结束 `fy4b-wp` 进程
3. 删除 exe
4. 如需彻底清理：删除数据目录 `%LOCALAPPDATA%\fy4b`（壁纸时间轴与日志）

### 源码运行（Linux / Windows）

需要 Python 3.10+：

```bash
git clone https://github.com/915P/FY4B.git
cd FY4B
pip install -r requirements.txt
python3 FY4B.py      # Linux（Windows 把这行换成 python FY4B.py）
```

- Windows 以正常模式启动时会自动注册开机自启；Linux 的开机运行由 deb 包的 autostart 负责，源码运行需自行保证开机拉起
- Windows 壁纸样式默认 Fit（保持比例缩放，等同 Linux 的 `scaled`），想改成铺满裁剪可把 `FY4B.py` 里的 `WINDOWS_WALLPAPER_STYLE` 改为 `"10"`

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

产物为仓库根目录下的 `fy4b-wp_<版本>_amd64.deb`，PyInstaller 中间产物在 `dist/`。

### exe + 安装包（Windows）

```powershell
.\build.bat
```

- `dist\fy4b-wp.exe`：单文件 exe（无控制台窗口，日志见 `%LOCALAPPDATA%\fy4b\cache\fy4b.log`）
- `dist\fy4b-wp-setup.exe`：图形安装包（需要 [Inno Setup 6](https://jrsoftware.org/isinfo.php)，未安装则跳过该步）

### 发布（Windows + Linux 双版本）

两个平台的产物都落在 `dist/`，**互不清掉**（`build.sh` 只清理 `build_deb/`、`build/` 与 `.spec`；
Linux 产物是 `dist/fy4b-wp`，与 Windows 的 `fy4b-wp.exe` / `fy4b-wp-setup.exe` 不同名）：

1. **Windows 侧**：`.\build.bat` → `dist\fy4b-wp.exe` + `dist\fy4b-wp-setup.exe`
2. **Linux 侧**：`bash build.sh` → `./fy4b-wp_<版本>_amd64.deb`
3. 一起发布（需已登录 `gh` CLI）：

```bash
gh release create v<版本> ./fy4b-wp_<版本>_amd64.deb \
    dist/fy4b-wp.exe dist/fy4b-wp-setup.exe \
    --title "FY4B Wallpaper <版本>" --notes "..."
```

发版前记得同步 `build.sh` 里的 `VERSION`。

## 测试

回归测试在 `tests/`：

```bash
# Linux（22 项：三项基础验证 + XDG 路径 + 命令行参数 + 单实例锁）
# 自带环境隔离：独立 HOME/TMPDIR + 假 gsettings，无需停守护进程，也不会真改壁纸
python3 tests/test_linux_support.py
```

```powershell
python tests/test_windows_support.py                # 39 项：代码与平台层
powershell -File tests\test_windows_install.ps1     # 26 项：免安装 exe 生命周期
powershell -File tests\test_installer.ps1           # 34 项：安装包（含零残留卸载）
```

Linux 脚本随时可跑（需联网下载云图）；Windows 前两个跑之前先停掉正在运行的 `fy4b-wp`（单实例锁），后两个会自己停、卸、装，结束后程序留在运行状态。

## 技术原理

- 数据源：国家卫星气象中心 FY-4B L1 全圆盘云图
- 使用 `APScheduler` 定时调度
- 使用 `Pillow` 处理大尺寸卫星云图
- 使用 `filelock` 保证单实例运行
- Linux 通过 `gsettings` / `xfconf-query` 等桌面命令设置壁纸；Windows 通过 `SystemParametersInfoW` + 注册表样式值设置壁纸

## 许可证

MIT License，见 [LICENSE](LICENSE)。