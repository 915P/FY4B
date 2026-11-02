# FY4B Wallpaper

自动下载 **风云四号 B 星 (FY-4B)** 静止轨道卫星云图并设置为桌面壁纸。

## 功能

- 定时下载 FY-4B 全圆盘云图（每小时的 10/25/40/55 分）
- 自动设置为桌面壁纸（支持 Cinnamon / GNOME / KDE / Xfce / MATE）
- 时间轴缓存：断网或下载失败时自动回退到本地最新壁纸
- 临时下载文件用完即删，启动时清理历史遗留文件，不会长期占用磁盘
- 单实例锁，避免重复运行
- 系统唤醒检测，挂起恢复后自动更新

## 数据存放位置

全部遵循 XDG 规范，不占用用户图片目录（可用 `XDG_DATA_HOME` / `XDG_CACHE_HOME` 覆盖）：

| 内容 | 路径 | 说明 |
| --- | --- | --- |
| 壁纸时间轴 | `~/.local/share/fy4b/timeline/` | 每小时 4 个槽位（`HH-10/25/40/55.jpg`），每天覆盖写入，占用有上限 |
| 临时下载 | `~/.cache/fy4b/downloads/` | 拷贝进时间轴后立即删除 |
| 日志 | `~/.cache/fy4b/fy4b.log` | |
| 单实例锁 | `~/.cache/fy4b/app.lock` | |

从旧版本（`~/Pictures/FY4B/timeline/`）升级时，首次启动会自动把已有壁纸迁移到新位置，并清理旧版本遗留在 `~/.cache/fy4b/` 下的原始下载文件。

## 安装

### 通过 deb 包安装（推荐）

从 [Releases](https://github.com/USER/FY4B/releases) 下载最新 `.deb` 包：

```bash
sudo dpkg -i fy4b-wp_*.deb
sudo apt install -f   # 安装依赖
```

安装后服务会自动启动，每 15 分钟更新壁纸。

### 手动运行

```bash
pip install -r requirements.txt
python3 FY4B.py
```

## 构建 deb 包

```bash
bash build.sh
```

产物在 `dist/` 目录下。

## 技术原理

- 数据源：国家卫星气象中心 FY-4B L1 全圆盘云图
- 使用 `APScheduler` 定时调度
- 使用 `Pillow` 处理大尺寸卫星云图
- 使用 `filelock` 保证单实例运行

## 许可证

MIT License，见 [LICENSE](LICENSE)。