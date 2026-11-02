#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import argparse
import datetime
import logging
import tempfile
import threading
import shutil

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from filelock import FileLock, Timeout
from PIL import Image

# ---------- 平台判定 ----------
IS_WINDOWS = sys.platform.startswith("win")

# ---------- 基本配置 ----------
DOWNLOAD_URL = "http://img.nsmc.org.cn/CLOUDIMAGE/FY4B/AGRI/GCLR/FY4B_DISK_GCLR.JPG"

# 数据源前有华为云 WAF，默认的 python-requests User-Agent 会被 418 拦截
REQUEST_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

# 用户主目录：Linux 读 $HOME，Windows 读 $USERPROFILE（HOME 在 Windows 上通常不存在）
HOME = os.path.expanduser("~")


def xdg_dir(env_name, fallback_subpath):
    """返回 XDG 目录下的 fy4b 数据目录（尊重 XDG_*_HOME 环境变量，仅 Linux 使用）"""
    base = os.environ.get(env_name) or os.path.join(HOME, fallback_subpath)
    return os.path.join(base, "fy4b")


def localappdata_dir(fallback_subpath):
    """返回 Windows 本地应用数据目录下的 fy4b 目录（尊重 %LOCALAPPDATA%）"""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(HOME, fallback_subpath)
    return os.path.join(base, "fy4b")


if IS_WINDOWS:
    # Windows：数据与缓存统一放在 %LOCALAPPDATA%\fy4b 下
    #   时间轴 %LOCALAPPDATA%\fy4b\timeline
    #   日志/锁 %LOCALAPPDATA%\fy4b\cache
    DATA_ROOT = localappdata_dir(os.path.join("AppData", "Local"))
    CACHE_ROOT = os.path.join(DATA_ROOT, "cache")
else:
    # 壁纸时间轴（XDG 数据目录，不放进用户图片目录）
    DATA_ROOT = xdg_dir("XDG_DATA_HOME", os.path.join(".local", "share"))
    # 日志与锁（XDG 缓存目录）
    CACHE_ROOT = xdg_dir("XDG_CACHE_HOME", ".cache")

TIMELINE_DIR = os.path.join(DATA_ROOT, "timeline")
LOCK_FILE = os.path.join(CACHE_ROOT, "app.lock")
LOG_FILE = os.path.join(CACHE_ROOT, "fy4b.log")

# 临时下载放在系统临时目录（Linux /tmp/fy4b，Windows %TEMP%\fy4b）：用完即删，
# 即使进程异常退出，关机后系统（Linux systemd-tmpfiles / Windows 磁盘清理）也会回收
DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "fy4b")
# 旧版本曾把临时文件放在缓存目录下
LEGACY_DOWNLOAD_DIR = os.path.join(CACHE_ROOT, "downloads")

# 旧版本的时间轴位置（用于一次性迁移；Windows 上不存在旧版本，判断会直接跳过）
LEGACY_TIMELINE_DIR = os.path.join(HOME, "Pictures", "FY4B", "timeline")

# 定义四个时间槽位（分钟）
SLOTS = [10, 25, 40, 55]

# 原图可能很大，设置允许的像素上限
Image.MAX_IMAGE_PIXELS = 300000000

# ---------- 创建必要目录 ----------
os.makedirs(CACHE_ROOT, exist_ok=True)
os.makedirs(TIMELINE_DIR, exist_ok=True)
try:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.chmod(DOWNLOAD_DIR, 0o700)  # 临时图片仅本人可读
except OSError:
    pass

# ---------- 单实例锁 ----------
lock = FileLock(LOCK_FILE, timeout=0)
try:
    lock.acquire()
except Timeout:
    # 窗口模式（PyInstaller --noconsole）下 sys.stdout 可能为 None
    try:
        print("已有实例在运行，退出本次进程。")
    except Exception:
        pass
    sys.exit(1)

# ---------- 日志初始化 ----------
if IS_WINDOWS:
    # Windows 控制台/重定向默认使用本地编码（如 GBK），日志里的中文和特殊
    # 字符会触发 UnicodeEncodeError，统一改成 UTF-8 输出
    for _stream in (sys.stdout, sys.stderr):
        try:
            if _stream is not None:
                _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def init_log():
    global logger
    logger = logging.getLogger("FY4B")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    # 日志文件固定用 UTF-8 写入（Windows 默认按本地编码写会乱码/报错）
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    # PyInstaller --noconsole 下 sys.stderr 可能为 None，回退到 devnull
    stream = sys.stderr if sys.stderr is not None else open(
        os.devnull, "w", encoding="utf-8", errors="replace")
    ch = logging.StreamHandler(stream)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

init_log()
logger.info("程序启动，日志输出至 %s", LOG_FILE)

# ---------- 清理历史遗留文件 ----------
RAW_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}\.jpg$")


def cleanup_downloads():
    """删除遗留的临时下载文件（崩溃/关机未清理的图片）"""
    removed = 0
    targets = [
        (DOWNLOAD_DIR, None),          # 当前版本：系统临时目录下的 fy4b
        (LEGACY_DOWNLOAD_DIR, None),   # 过渡版本：缓存目录下的 downloads
        (CACHE_ROOT, RAW_NAME_RE),     # 旧版本：缓存目录下的 2026-..jpg
    ]

    for directory, pattern in targets:
        try:
            for name in os.listdir(directory):
                path = os.path.join(directory, name)
                if not os.path.isfile(path):
                    continue
                if pattern is not None and not pattern.match(name):
                    continue
                os.remove(path)
                removed += 1
        except OSError:
            continue
    if removed:
        logger.info(f"已清理 {removed} 个遗留临时下载文件")


def migrate_legacy_timeline():
    """把旧版本 ~/Pictures/FY4B/timeline 的图片迁移到新的时间轴目录"""
    if not os.path.isdir(LEGACY_TIMELINE_DIR):
        return
    moved = 0
    try:
        for name in os.listdir(LEGACY_TIMELINE_DIR):
            src = os.path.join(LEGACY_TIMELINE_DIR, name)
            dst = os.path.join(TIMELINE_DIR, name)
            if not os.path.isfile(src):
                continue
            if os.path.exists(dst):
                # 目标已存在则以较新的为准
                if os.path.getmtime(src) <= os.path.getmtime(dst):
                    os.remove(src)
                    continue
                os.remove(dst)
            shutil.move(src, dst)
            moved += 1
        # 迁移后移除已清空的旧目录
        for legacy_dir in (LEGACY_TIMELINE_DIR, os.path.dirname(LEGACY_TIMELINE_DIR)):
            if os.path.isdir(legacy_dir) and not os.listdir(legacy_dir):
                os.rmdir(legacy_dir)
    except OSError as e:
        logger.warning(f"迁移旧时间轴失败: {e}")
        return
    if moved:
        logger.info(f"已将 {moved} 张旧壁纸从 {LEGACY_TIMELINE_DIR} 迁移至 {TIMELINE_DIR}")


cleanup_downloads()
migrate_legacy_timeline()

# ---------- 获取当前时间所属槽位 ----------
def get_time_slot():
    now = datetime.datetime.now()
    minute = now.minute
    if minute < 10:
        return "55"
    for slot in sorted(SLOTS, reverse=True):
        if minute >= slot:
            return str(slot)
    return "55"

def get_timeline_filename():
    """生成当前时间对应的缓存文件名（如 10-25.jpg）"""
    now = datetime.datetime.now()
    hour = now.strftime("%H")
    slot = get_time_slot()
    return f"{hour}-{slot}.jpg"

# ---------- 下载功能 ----------
def download_wallpaper():
    retry = 0
    max_retry = 5
    while retry < max_retry:
        try:
            logger.info("开始下载 FY‑4B 云图...")
            resp = requests.get(DOWNLOAD_URL, timeout=30,
                                headers=REQUEST_HEADERS)
            resp.raise_for_status()
            raw_name = time.strftime("%Y-%m-%d_%H-%M") + ".jpg"
            raw_path = os.path.join(DOWNLOAD_DIR, raw_name)
            with open(raw_path, "wb") as f:
                f.write(resp.content)
            logger.info(f"下载成功，临时文件: {raw_path}")
            return raw_path
        except requests.exceptions.RequestException as e:
            retry += 1
            logger.error(f"下载失败 ({e})，第 {retry}/{max_retry} 次重试...")
            time.sleep(3)
    logger.error("下载重试次数用尽，放弃下载")
    return None

# ---------- 保存原始图片到对应槽位（带小时） ----------
def save_to_timeline(raw_path):
    filename = get_timeline_filename()
    out_path = os.path.join(TIMELINE_DIR, filename)
    try:
        shutil.copy2(raw_path, out_path)
        logger.info(f"原始图片已保存至 {out_path}")
        return out_path
    except Exception as e:
        logger.error(f"保存缓存失败: {e}")
        return None

# ---------- 删除临时下载文件（避免长期占用磁盘） ----------
def remove_download(raw_path):
    try:
        os.remove(raw_path)
        logger.info(f"已删除临时文件 {raw_path}")
    except OSError as e:
        logger.warning(f"删除临时文件失败 {raw_path}: {e}")

# ---------- 设置壁纸（Linux 桌面 / Windows） ----------
# Windows 壁纸样式值：6 = Fit（保持比例缩放，等同 Linux 的 scaled），
#                     10 = Fill（铺满裁剪，Windows 默认）
WINDOWS_WALLPAPER_STYLE = "6"


def set_wallpaper_windows(image_abs):
    """Windows：先写样式注册表，再用 SystemParametersInfoW 设置壁纸"""
    import ctypes
    import winreg

    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02

    try:
        # 样式必须先写好，紧随其后的 SPI 调用才会按新样式渲染
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop",
            0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, WINDOWS_WALLPAPER_STYLE)
            winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")

        func = ctypes.windll.user32.SystemParametersInfoW
        func.argtypes = (ctypes.c_uint, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint)
        func.restype = ctypes.c_bool
        ok = func(SPI_SETDESKWALLPAPER, 0, image_abs,
                  SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)
        if not ok:
            logger.error(f"SystemParametersInfoW 调用失败 (GetLastError={ctypes.GetLastError()})")
            return False
        logger.info(f"壁纸已设置为 {image_abs} (样式: fit)")
        return True
    except (OSError, AttributeError, TypeError, ValueError) as e:
        logger.error(f"设置壁纸异常: {e}")
        return False


def set_wallpaper(image_path):
    if not os.path.exists(image_path):
        logger.warning(f"壁纸文件不存在: {image_path}")
        return False

    image_abs = os.path.abspath(image_path)

    if IS_WINDOWS:
        return set_wallpaper_windows(image_abs)

    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()

    try:
        if "cinnamon" in desktop:
            cmd_uri = f"gsettings set org.cinnamon.desktop.background picture-uri 'file://{image_abs}'"
            os.system(cmd_uri)
            os.system("gsettings set org.cinnamon.desktop.background picture-options 'scaled'")
            logger.info(f"壁纸已设置为 {image_path} (模式: scaled)")
            return True
        elif "gnome" in desktop or "ubuntu" in desktop:
            cmd = f"gsettings set org.gnome.desktop.background picture-uri 'file://{image_abs}'"
            os.system(cmd)
            os.system("gsettings set org.gnome.desktop.background picture-options 'scaled'")
            return True
        elif "mate" in desktop:
            cmd = f"gsettings set org.mate.background picture-filename '{image_abs}'"
            os.system(cmd)
            return True
        elif "xfce" in desktop:
            cmd = f"xfconf-query -c xfce4-desktop -p /backdrop/screen0/monitor0/image-path -s '{image_abs}'"
            os.system(cmd)
            return True
        elif "kde" in desktop or "plasma" in desktop:
            cmd = f"plasma-apply-wallpaperimage '{image_abs}'"
            os.system(cmd)
            return True
        else:
            logger.warning(f"未识别的桌面环境 '{desktop}'，尝试使用 feh")
            cmd = f"feh --bg-scale '{image_abs}'"
            os.system(cmd)
            return True
    except Exception as e:
        logger.error(f"设置壁纸异常: {e}")
        return False

# ---------- 根据当前时间查找缓存（带小时） ----------
def find_latest_cached():
    """返回时间轴中最近保存的一张图片（断网兜底）"""
    try:
        names = [
            n for n in os.listdir(TIMELINE_DIR)
            if n.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
    except OSError as e:
        logger.warning(f"读取时间轴目录失败: {e}")
        return None
    paths = [os.path.join(TIMELINE_DIR, n) for n in names]
    paths = [p for p in paths if os.path.isfile(p)]
    if not paths:
        return None
    return max(paths, key=os.path.getmtime)


def find_cached_by_time():
    """优先取当前槽位的图片；该槽位不存在时回退到时间轴中最新的一张"""
    exact = os.path.join(TIMELINE_DIR, get_timeline_filename())
    latest = find_latest_cached()
    if os.path.exists(exact):
        # 跨小时/跨天时 exact 可能是很早以前留下的，取时间上更新的那张
        if latest is None or os.path.getmtime(exact) >= os.path.getmtime(latest):
            return exact
    return latest

# ---------- 主更新流程 ----------
def update():
    logger.info("========== 开始壁纸更新 ==========")
    slot = get_time_slot()
    logger.info(f"当前时间映射到槽位: {slot}")

    raw = download_wallpaper()
    saved = None
    if raw is not None:
        saved = save_to_timeline(raw)
        # 无论保存成功与否，临时下载文件都不留在磁盘上
        remove_download(raw)

    if saved and set_wallpaper(saved):
        return

    cached = find_cached_by_time()
    if cached:
        if raw is None:
            reason = "下载失败"
        elif saved is None:
            reason = "保存失败"
        else:
            reason = "设置壁纸失败"
        logger.info(f"{reason}，改用本地缓存壁纸: {cached}")
        set_wallpaper(cached)
    else:
        logger.warning("下载失败且本地无可用缓存，壁纸未更新")

# ---------- 唤醒监控线程 ----------
def watch_wake():
    last = datetime.datetime.now()
    while True:
        time.sleep(5)
        now = datetime.datetime.now()
        if (now - last) > datetime.timedelta(minutes=1):
            logger.info("检测到系统挂起/唤醒，重置调度器")
            try:
                if not scheduler.running:
                    logger.warning("调度器未运行，重启")
                    scheduler.start()
                job = scheduler.get_job("update_wallpaper")
                if job:
                    job.modify(next_run_time=datetime.datetime.now())
                else:
                    logger.error("找不到任务 'update_wallpaper'")
            except Exception as e:
                logger.error(f"唤醒处理失败: {e}", exc_info=True)
        last = now

# ---------- 开机自启（Windows 注册表 Run 键） ----------
AUTOSTART_NAME = "fy4b-wp"
AUTOSTART_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_command():
    """返回开机自启要执行的命令行（PyInstaller 单文件直接用自身路径）"""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # 源码运行时优先用 pythonw.exe，避免登录时弹出控制台窗口
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        pythonw = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(pythonw):
            exe = pythonw
    return f'"{exe}" "{os.path.abspath(__file__)}"'


def register_autostart():
    """把本程序写入 HKCU Run 键实现开机自启（幂等，重复启动只覆盖）"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ,
                              autostart_command())
        logger.info("已注册开机自启")
        return True
    except (OSError, ImportError) as e:
        logger.warning(f"注册开机自启失败: {e}")
        return False


def unregister_autostart():
    """从 HKCU Run 键移除开机自启项（项不存在时静默通过）"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY,
                            0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, AUTOSTART_NAME)
            except FileNotFoundError:
                pass
        logger.info("已移除开机自启项")
        return True
    except (OSError, ImportError) as e:
        logger.warning(f"移除开机自启项失败: {e}")
        return False


# ---------- 命令行参数 ----------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="fy4b-wp",
        description="下载 FY-4B 云图并设置为桌面壁纸")
    parser.add_argument("--once", action="store_true",
                        help="只执行一次更新后退出（用于测试）")
    parser.add_argument("--remove-autostart", action="store_true",
                        help="移除开机自启项后退出（仅 Windows）")
    return parser.parse_args(argv)


# ---------- 主程序 ----------
scheduler = None


def main(argv=None):
    global scheduler
    args = parse_args(argv)

    if args.remove_autostart:
        if IS_WINDOWS:
            unregister_autostart()
        else:
            logger.info("Linux 的开机自启由 deb 包（/etc/xdg/autostart）管理，无需代码处理")
        return 0

    if args.once:
        # 测试模式：只跑一次更新，不注册自启也不启动调度器
        update()
        shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)
        return 0

    if IS_WINDOWS:
        # Windows 没有 deb 那样的系统级 autostart，启动时自动注册到 HKCU Run 键
        register_autostart()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        update,
        "cron",
        minute="10,25,40,55",
        id="update_wallpaper",
        replace_existing=True
    )

    threading.Thread(target=watch_wake, daemon=True).start()

    scheduler.start()
    logger.info("调度器已启动，将在每小时的 10,25,40,55 分更新壁纸")

    # 立即执行一次
    update()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭调度器...")
        scheduler.shutdown()
        logger.info("调度器已关闭")
        # 正常退出时清空临时目录
        shutil.rmtree(DOWNLOAD_DIR, ignore_errors=True)
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())