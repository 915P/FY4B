# -*- coding: utf-8 -*-
"""FY4B Windows 支持验证脚本（回归测试，已入库：tests/test_windows_support.py）

覆盖 AGENTS.md 要求的验证项：
  1. 静态编译 py_compile
  2. 离线回退：patch download_wallpaper -> None，patch set_wallpaper，
     断言拿到 TIMELINE_DIR 内 mtime 最新的图
  3. 临时文件不残留：真实 update() 后临时目录为空
外加 Windows 专属：路径解析、SystemParametersInfoW、注册表自启动、参数解析。

用法（需先停掉正在运行的 fy4b-wp，否则导入时抢不到单实例锁）：
    python tests/test_windows_support.py
"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import winreg

# 仓库根目录 = 本文件所在目录的上一级（避免硬编码机器路径）
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import FY4B  # noqa: E402  （导入即建目录、取单实例锁）

PASS = []
FAIL = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    (PASS if cond else FAIL).append(name)
    print(f"[{tag}] {name}" + (f"  -- {detail}" if detail and not cond else ""))


def section(title):
    print("\n===== " + title + " =====")


# ---------------- 1. 静态编译 ----------------
section("1. py_compile")
rc = subprocess.run([sys.executable, "-m", "py_compile",
                     os.path.join(REPO, "FY4B.py")]).returncode
check("py_compile FY4B.py", rc == 0)

# ---------------- 2. 路径解析 ----------------
section("2. Windows 路径")
localappdata = os.environ["LOCALAPPDATA"]
check("HOME 未抛 KeyError", bool(FY4B.HOME), FY4B.HOME)
check("DATA_ROOT = %LOCALAPPDATA%\\fy4b",
      FY4B.DATA_ROOT == os.path.join(localappdata, "fy4b"), FY4B.DATA_ROOT)
check("TIMELINE_DIR 在 LOCALAPPDATA 下",
      FY4B.TIMELINE_DIR == os.path.join(localappdata, "fy4b", "timeline"), FY4B.TIMELINE_DIR)
check("CACHE_ROOT = %LOCALAPPDATA%\\fy4b\\cache",
      FY4B.CACHE_ROOT == os.path.join(localappdata, "fy4b", "cache"), FY4B.CACHE_ROOT)
check("LOG_FILE 在 cache 下", FY4B.LOG_FILE.startswith(FY4B.CACHE_ROOT), FY4B.LOG_FILE)
check("临时目录用系统 TEMP",
      FY4B.DOWNLOAD_DIR == os.path.join(os.environ["TEMP"], "fy4b"), FY4B.DOWNLOAD_DIR)
check("IS_WINDOWS = True", FY4B.IS_WINDOWS)
check("目录已创建", all(os.path.isdir(p) for p in
                        (FY4B.DATA_ROOT, FY4B.TIMELINE_DIR, FY4B.CACHE_ROOT, FY4B.DOWNLOAD_DIR)))

# ---------------- 3. 离线回退（AGENTS 验证项 2） ----------------
section("3. 离线回退")
seeded = None
if not FY4B.find_latest_cached():
    seeded = os.path.join(FY4B.TIMELINE_DIR, "00-00.jpg")
    with open(seeded, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0fake")   # 仅用于存在性判断

calls = []
orig_download, orig_setwall = FY4B.download_wallpaper, FY4B.set_wallpaper
FY4B.download_wallpaper = lambda: None
FY4B.set_wallpaper = lambda p: calls.append(p) or True
FY4B.update()
FY4B.download_wallpaper, FY4B.set_wallpaper = orig_download, orig_setwall

newest = FY4B.find_latest_cached()
check("下载失败时仍回退到本地缓存", len(calls) == 1, f"set_wallpaper 调用次数={len(calls)}")
check("回退拿到的是 mtime 最新的图",
      len(calls) == 1 and calls[0] == newest, f"got={calls[:1]} newest={newest}")
check("回退目标在 TIMELINE_DIR 内",
      len(calls) == 1 and os.path.dirname(calls[0]) == FY4B.TIMELINE_DIR, calls[:1])
if seeded and os.path.exists(seeded):
    os.remove(seeded)

# ---------------- 4. 真实 update()：下载 + 临时文件不残留（AGENTS 验证项 3） ----------------
section("4. 真实 update()（联网下载，不真的改壁纸）")
import requests  # noqa: E402
try:
    r = requests.get(FY4B.DOWNLOAD_URL, timeout=(10, 20),
                     headers=FY4B.REQUEST_HEADERS)
    ok_net = r.status_code == 200 and len(r.content) > 100000
    check("数据源可达（带 WAF 需要的 UA）", ok_net,
          f"status={r.status_code} len={len(r.content)}")
except Exception as e:                                    # noqa: BLE001
    check("数据源可达（带 WAF 需要的 UA）", False, repr(e))

def dir_state(d):
    return {n: os.path.getmtime(os.path.join(d, n))
            for n in os.listdir(d) if os.path.isfile(os.path.join(d, n))}


wall_calls = []
FY4B.set_wallpaper = lambda p: wall_calls.append(p) or True   # 只记录，不真改壁纸
before = dir_state(FY4B.TIMELINE_DIR)
t0 = time.time()
FY4B.update()
elapsed = time.time() - t0
FY4B.set_wallpaper = orig_setwall

after = dir_state(FY4B.TIMELINE_DIR)
new_files = set(after) - set(before)
# 同一时间槽位内重跑会覆盖同名文件，因此“新增文件名”或“同名文件 mtime 变新”都算写入
touched = [n for n in after if n not in before or after[n] > before[n] + 0.001]
check("临时目录为空", os.listdir(FY4B.DOWNLOAD_DIR) == [],
      str(os.listdir(FY4B.DOWNLOAD_DIR)))
check("时间轴已写入（新增或同槽位覆盖）", len(touched) >= 1,
      f"新增={sorted(new_files)} 变化={sorted(touched)}")
check("set_wallpaper 拿到的图有效",
      len(wall_calls) == 1 and os.path.isfile(wall_calls[0])
      and os.path.getsize(wall_calls[0]) > 100000, str(wall_calls))
check("set_wallpaper 被调用", len(wall_calls) == 1, str(wall_calls))
print(f"      update() 耗时 {elapsed:.1f}s")

# ---------------- 5. Windows 壁纸设置（mock SPI，不真改壁纸） ----------------
section("5. set_wallpaper_windows（mock 掉真实调用）")


class _FakeReg:
    """伪注册表句柄：作为 OpenKey 的返回值，配合 context manager 使用"""
    def __init__(self):
        self.writes = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


fake_reg = _FakeReg()
spi_calls = []


def fake_spi(action, ui_param, path, flags):
    spi_calls.append((action, ui_param, path, flags))
    return True


def fake_setvalue(key, name, reserved, regtype, value):
    # 记录 (键, 名称, 保留, 类型, 值)，不真正写注册表
    fake_reg.writes.append((key, name, reserved, regtype, value))
    return None


orig_openkey, orig_setvalueex = winreg.OpenKey, winreg.SetValueEx
orig_spi = ctypes.windll.user32.SystemParametersInfoW
winreg.OpenKey = lambda *a, **k: fake_reg
winreg.SetValueEx = fake_setvalue
ctypes.windll.user32.SystemParametersInfoW = fake_spi
try:
    tmp_img = os.path.join(FY4B.DOWNLOAD_DIR, "spi_test.jpg")
    with open(tmp_img, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0fake")
    ok = FY4B.set_wallpaper(tmp_img)
    check("set_wallpaper 返回 True", ok is True)
    check("调用了 SystemParametersInfoW", len(spi_calls) == 1, str(spi_calls))
    if spi_calls:
        action, ui_param, path, flags = spi_calls[0]
        check("SPI action = SPI_SETDESKWALLPAPER(0x14)", action == 0x14, hex(action))
        check("SPI 路径是绝对路径", os.path.isabs(path), path)
        check("SPI flags 含 UPDATEINIFILE|SENDCHANGE", flags == 0x03, hex(flags))
    names = [(w[1], w[4]) for w in fake_reg.writes]
    check("写入 WallpaperStyle=6 (Fit)",
          ("WallpaperStyle", "6") in names, str(names))
    check("写入 TileWallpaper=0",
          ("TileWallpaper", "0") in names, str(names))
    check("文件不存在时返回 False", FY4B.set_wallpaper(
        os.path.join(FY4B.DOWNLOAD_DIR, "nope.jpg")) is False)
    os.remove(tmp_img)
finally:
    winreg.OpenKey, winreg.SetValueEx = orig_openkey, orig_setvalueex
    ctypes.windll.user32.SystemParametersInfoW = orig_spi

# ---------------- 6. 自启动注册表 ----------------
section("6. 开机自启（真实写入 HKCU Run 后立刻删除，不留残留）")
RUN_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"


def reg_query_value(value_name):
    """返回 (returncode, 文本)；reg query 输出是本地编码，按 UTF-8 容错解码"""
    q = subprocess.run(["reg", "query", RUN_KEY, "/v", value_name],
                       capture_output=True)
    text = (q.stdout + q.stderr).decode("utf-8", errors="replace")
    return q.returncode, text


cmd = FY4B.autostart_command()
check("自启动命令带引号", cmd.startswith('"') and cmd.count('"') >= 4, cmd)
check("自启动命令指向本脚本/解释器",
      os.path.basename(FY4B.__file__) in cmd or getattr(sys, "frozen", False), cmd)

ok_reg = FY4B.register_autostart()
check("register_autostart() 成功", ok_reg)
try:
    rc_q, out_q = reg_query_value(FY4B.AUTOSTART_NAME)
    check("reg query 能查到 fy4b-wp", rc_q == 0 and FY4B.AUTOSTART_NAME in out_q, out_q)
    check("Run 值内容与 autostart_command 一致",
          rc_q == 0 and cmd in " ".join(out_q.split()), out_q)
finally:
    FY4B.unregister_autostart()          # 清理，避免测试改变系统状态

rc_q2, out_q2 = reg_query_value(FY4B.AUTOSTART_NAME)
check("unregister_autostart() 后已删除", rc_q2 != 0, out_q2)
check("重复 unregister 幂等", FY4B.unregister_autostart() is True)

# ---------------- 7. 命令行参数 ----------------
section("7. 命令行参数")
check("--once 解析", FY4B.parse_args(["--once"]).once is True)
check("--remove-autostart 解析",
      FY4B.parse_args(["--remove-autostart"]).remove_autostart is True)
check("默认无参", FY4B.parse_args([]).once is False and
      FY4B.parse_args([]).remove_autostart is False)

# --remove-autostart 真实跑一遍（此时应无自启动项，静默通过）
rc = FY4B.main(["--remove-autostart"])
check("main(['--remove-autostart']) 返回 0", rc == 0)

# --once：patch 掉 update，确认不注册自启、不启动调度器
once_calls = []
orig_register, orig_update = FY4B.register_autostart, FY4B.update
FY4B.register_autostart = lambda: once_calls.append("register") or True
FY4B.update = lambda: once_calls.append("update")
rc = FY4B.main(["--once"])
FY4B.register_autostart, FY4B.update = orig_register, orig_update
check("main(['--once']) 返回 0", rc == 0)
check("--once 执行了 update 且未注册自启", once_calls == ["update"], str(once_calls))
leftover = os.listdir(FY4B.DOWNLOAD_DIR) if os.path.isdir(FY4B.DOWNLOAD_DIR) else []
check("临时目录被清空", leftover == [], str(leftover))

# ---------------- 汇总 ----------------
print("\n===== 汇总 =====")
print(f"PASS {len(PASS)} / FAIL {len(FAIL)}")
if FAIL:
    for n in FAIL:
        print("  失败: " + n)
sys.exit(1 if FAIL else 0)