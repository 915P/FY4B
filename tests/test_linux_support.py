# -*- coding: utf-8 -*-
"""FY4B Linux 回归测试（与 tests/test_windows_support.py 对偶）

覆盖 AGENTS.md 要求的 Linux 三项验证 + 跨平台改动的回归：
  1. 静态编译 py_compile
  2. 离线回退：patch download_wallpaper -> None，patch set_wallpaper，
     断言拿到 TIMELINE_DIR 内 mtime 最新的图
  3. 临时文件不残留：真实 update() 后临时目录里没有遗留文件
  4. XDG 路径未被 Windows 平台层污染
  5. 命令行参数（--help / --once / --remove-autostart）与单实例锁

用法：
    python3 tests/test_linux_support.py

隔离手段（因此**无需停掉正在运行的 fy4b-wp**，也不会改真实桌面）：
  - 独立 HOME / XDG_* / TMPDIR → 不碰真实数据、不与守护进程抢单实例锁
  - PATH 前置假 gsettings / feh → 真实走 Linux 设壁纸分支，但只记录参数不动桌面
  - 需要真实网络（数据源下载约 4MB，耗时 25~70 秒）
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

# 仓库根目录 = 本文件所在目录的上一级（避免硬编码机器路径）
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- 环境隔离（必须在 import FY4B 之前） ----------
ISO = tempfile.mkdtemp(prefix="fy4b-linux-test-")
HOME_DIR = os.path.join(ISO, "home")
TMP_DIR = os.path.join(ISO, "tmp")
BIN_DIR = os.path.join(ISO, "bin")
CALLS_LOG = os.path.join(ISO, "calls.log")
for _d in (HOME_DIR, TMP_DIR, BIN_DIR):
    os.makedirs(_d, exist_ok=True)

# 假 gsettings / feh：记录调用参数、返回成功，但不动真实桌面
for _tool in ("gsettings", "feh"):
    _path = os.path.join(BIN_DIR, _tool)
    with open(_path, "w") as _f:
        _f.write('#!/bin/sh\nprintf "%%s\\n" "%s $@" >> "%s"\n' % (_tool, CALLS_LOG))
    os.chmod(_path, 0o755)

os.environ["HOME"] = HOME_DIR
os.environ["XDG_DATA_HOME"] = os.path.join(HOME_DIR, ".local", "share")
os.environ["XDG_CACHE_HOME"] = os.path.join(HOME_DIR, ".cache")
os.environ["TMPDIR"] = TMP_DIR
os.environ["PATH"] = BIN_DIR + os.pathsep + os.environ["PATH"]
os.environ["XDG_CURRENT_DESKTOP"] = "Cinnamon"
os.environ.pop("LOCALAPPDATA", None)

# 上面的 tempfile.mkdtemp() 已经把 gettempdir() 的结果缓存成 /tmp，
# 必须清掉缓存，否则 FY4B 的 DOWNLOAD_DIR 会落进真实 /tmp/fy4b，
# 测试可能误删正在运行的守护进程的临时文件
tempfile.tempdir = None

# 子进程的 HOME 也被隔离了，用户 site-packages 会失效，
# 这里把真实用户库路径补进 PYTHONPATH（只影响测试，不影响被测代码）
SUB_ENV = dict(os.environ)
try:
    import pwd
    _real_home = pwd.getpwuid(os.getuid()).pw_dir
    _user_site = os.path.join(_real_home, ".local", "lib",
                              "python%d.%d" % sys.version_info[:2], "site-packages")
    SUB_ENV["PYTHONPATH"] = _user_site + os.pathsep + SUB_ENV.get("PYTHONPATH", "")
except ImportError:  # 非 POSIX（理论上不会走到）
    pass

sys.path.insert(0, REPO)
import FY4B  # noqa: E402  （导入即建目录、取单实例锁）

# 硬性防线：隔离失败就立刻中止，绝不允许污染真实 /tmp 与真实家目录
for _p in (FY4B.DOWNLOAD_DIR, FY4B.TIMELINE_DIR, FY4B.CACHE_ROOT):
    assert _p.startswith(ISO), f"环境隔离失败，拒绝继续: {_p}"

PASS = []


def check(name, cond, detail=""):
    ok = bool(cond)
    print(("[PASS] " if ok else "[FAIL] ") + name + (f"  -- {detail}" if detail and not ok else ""))
    PASS.append(ok)


def section(title):
    print("\n===== " + title + " =====")


def no_leftover():
    """临时目录里不应有遗留文件；目录整体不存在也算干净（退出时会 rmtree）"""
    if not os.path.isdir(FY4B.DOWNLOAD_DIR):
        return True, "目录已被清理"
    files = os.listdir(FY4B.DOWNLOAD_DIR)
    return files == [], str(files)


try:
    # ---------------- 1. 静态编译 ----------------
    section("1. py_compile")
    rc = subprocess.run([sys.executable, "-m", "py_compile",
                         os.path.join(REPO, "FY4B.py")]).returncode
    check("py_compile FY4B.py", rc == 0)

    # ---------------- 2. 路径：Linux 不受 Windows 平台层影响 ----------------
    section("2. XDG 路径")
    check("IS_WINDOWS = False", FY4B.IS_WINDOWS is False)
    check("DATA_ROOT 走 XDG",
          FY4B.DATA_ROOT == os.path.join(HOME_DIR, ".local", "share", "fy4b"), FY4B.DATA_ROOT)
    check("CACHE_ROOT 走 XDG",
          FY4B.CACHE_ROOT == os.path.join(HOME_DIR, ".cache", "fy4b"), FY4B.CACHE_ROOT)
    check("TIMELINE_DIR = DATA_ROOT/timeline",
          FY4B.TIMELINE_DIR == os.path.join(FY4B.DATA_ROOT, "timeline"), FY4B.TIMELINE_DIR)
    check("下载目录 = 系统临时目录/fy4b",
          FY4B.DOWNLOAD_DIR == os.path.join(TMP_DIR, "fy4b"), FY4B.DOWNLOAD_DIR)
    check("LEGACY_TIMELINE_DIR 在 HOME/Pictures 下",
          FY4B.LEGACY_TIMELINE_DIR.startswith(HOME_DIR))

    fh = [h for h in FY4B.logger.handlers if isinstance(h, __import__("logging").FileHandler)]
    check("日志文件句柄 UTF-8",
          bool(fh) and getattr(fh[0].stream, "encoding", "").lower() in ("utf-8", "utf8"),
          getattr(fh[0].stream, "encoding", None) if fh else "无 FileHandler")

    # ---------------- 3. 离线回退 ----------------
    section("3. 离线回退（AGENTS.md 第 2 项）")
    real_download = FY4B.download_wallpaper          # 先存住真实实现
    shutil.rmtree(FY4B.TIMELINE_DIR, ignore_errors=True)
    os.makedirs(FY4B.TIMELINE_DIR, exist_ok=True)
    old = os.path.join(FY4B.TIMELINE_DIR, "00-55.jpg")
    with open(old, "wb") as f:
        f.write(b"old-image")
    os.utime(old, (time.time() - 7200, time.time() - 7200))

    set_calls = []
    FY4B.set_wallpaper = lambda p: (set_calls.append(p), True)[1]
    FY4B.download_wallpaper = lambda: None
    FY4B.update()
    check("下载失败时回退到本地缓存", len(set_calls) == 1, str(set_calls))
    check("命中 TIMELINE_DIR 内 mtime 最新的图", set_calls == [old],
          set_calls[0] if set_calls else "无")

    # ---------------- 4. 真实 update() + 临时文件不残留 ----------------
    section("4. 真实更新（AGENTS.md 第 3 项）")
    FY4B.download_wallpaper = real_download          # 还原真实下载
    set_calls.clear()
    FY4B.update()
    check("真实 update() 设置了壁纸", len(set_calls) == 1, str(set_calls))
    ok, detail = no_leftover()
    check("临时目录无遗留文件", ok, detail)
    check("时间轴写入了图片",
          bool(set_calls) and os.path.isfile(set_calls[0])
          and os.path.getsize(set_calls[0]) > 1000,
          set_calls[0] if set_calls else "无（应回退说明下载失败）")

    # ---------------- 5. 启动清理 ----------------
    section("5. 启动清理")
    fake = os.path.join(FY4B.CACHE_ROOT, "2020-01-01_00-00.jpg")
    os.makedirs(FY4B.CACHE_ROOT, exist_ok=True)
    with open(fake, "wb") as f:
        f.write(b"x")
    FY4B.cleanup_downloads()
    check("cleanup_downloads 清掉旧版临时图", not os.path.exists(fake))
    check("迁移函数可调用", callable(FY4B.migrate_legacy_timeline))

    # ---------------- 6. 命令行参数 ----------------
    section("6. 命令行参数（维护模式不抢单实例锁）")
    FY4B.lock.release()
    r = subprocess.run([sys.executable, os.path.join(REPO, "FY4B.py"), "--help"],
                       capture_output=True, text=True, env=SUB_ENV)
    check("--help 正常退出且列出 --once", r.returncode == 0 and "--once" in r.stdout,
          (r.stderr or "")[-200:])
    check("--help 不抢单实例锁（维护模式）", "已有实例在运行" not in (r.stdout + r.stderr))

    r2 = subprocess.run([sys.executable, os.path.join(REPO, "FY4B.py"), "--once"],
                        capture_output=True, text=True, env=SUB_ENV, timeout=300)
    check("--once 正常退出", r2.returncode == 0, (r2.stderr or "")[-300:])
    ok, detail = no_leftover()
    check("--once 退出后无临时文件残留", ok, detail)
    # --once 走的是真实 set_wallpaper，应命中假 gsettings（Linux 分支）而非 feh
    log = open(CALLS_LOG).read() if os.path.isfile(CALLS_LOG) else ""
    check("--once 走 Linux gsettings 分支", "gsettings" in log, log[-200:] or "无调用记录")

    r3 = subprocess.run([sys.executable, os.path.join(REPO, "FY4B.py"), "--remove-autostart"],
                        capture_output=True, text=True, env=SUB_ENV)
    check("--remove-autostart 在 Linux 上友好退出",
          r3.returncode == 0 and "autostart" in (r3.stdout + r3.stderr),
          (r3.stdout + r3.stderr)[-200:])

    # ---------------- 7. 单实例锁 ----------------
    section("7. 单实例锁")
    holder = subprocess.Popen(
        [sys.executable, "-c",
         "import sys,time; sys.path.insert(0,%r); import FY4B; "
         "print('LOCKED', flush=True); time.sleep(8)" % REPO],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=SUB_ENV)
    holder.stdout.readline()
    r4 = subprocess.run([sys.executable, "-c",
                         "import sys; sys.path.insert(0, %r); import FY4B" % REPO],
                        capture_output=True, text=True, env=SUB_ENV, timeout=60)
    holder.wait(timeout=30)
    check("并发导入被单实例锁挡下",
          r4.returncode == 1 and "已有实例在运行" in (r4.stdout + r4.stderr),
          (r4.stdout + r4.stderr)[-200:])
finally:
    shutil.rmtree(ISO, ignore_errors=True)

print("\n结果: %d/%d 通过" % (sum(PASS), len(PASS)))
sys.exit(0 if all(PASS) else 1)