#!/bin/bash
set -e

# ---------- 配置 ----------
APP_NAME="fy4b-wp"
VERSION="2026.11.02"
MAINTAINER="915P"
DESCRIPTION="FY-4B satellite cloud image wallpaper updater"
ARCH="amd64"

# ---------- 准备目录 ----------
BUILD_DIR="build_deb"
DEB_DIR="${BUILD_DIR}/${APP_NAME}_${VERSION}_${ARCH}"
DIST_DIR="dist"

# 清理旧构建
# 注意：不清理 dist/ —— 本仓库目录可能与 Windows 共用（挂载共享），
# dist/ 里躺着 Windows 打好的 fy4b-wp.exe 与 fy4b-wp-setup.exe，
# 清掉就无法从 git 恢复（它们是被忽略的产物）。
# Linux 产物文件名是 dist/fy4b-wp（无扩展名），与 Windows 的 .exe 不冲突，
# pyinstaller 每次都会覆盖写入，无需预清。
rm -rf "$BUILD_DIR" build "${APP_NAME}.spec"
mkdir -p "$DEB_DIR/DEBIAN"
mkdir -p "$DEB_DIR/usr/local/bin"
mkdir -p "$DEB_DIR/etc/xdg/autostart"

# ---------- 编译二进制（PyInstaller） ----------
echo "==> 编译二进制文件 ..."
pyinstaller --onefile --name "$APP_NAME" FY4B.py
if [ ! -f "$DIST_DIR/$APP_NAME" ]; then
    echo "错误：编译失败，未找到 $DIST_DIR/$APP_NAME"
    exit 1
fi

# 复制二进制到 DEB 包
cp "$DIST_DIR/$APP_NAME" "$DEB_DIR/usr/local/bin/"
chmod 755 "$DEB_DIR/usr/local/bin/$APP_NAME"

# ---------- 创建 autostart .desktop 文件 ----------
cat > "$DEB_DIR/etc/xdg/autostart/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Type=Application
Name=FY-4B Wallpaper Updater
Comment=Download and set FY-4B cloud image as wallpaper
Exec=/usr/local/bin/${APP_NAME}
X-GNOME-Autostart-enabled=true
EOF
chmod 644 "$DEB_DIR/etc/xdg/autostart/${APP_NAME}.desktop"

# ---------- 创建 DEBIAN/control ----------
cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Maintainer: $MAINTAINER
Depends: libc6, libx11-6, libxext6, libjpeg62-turbo, libpng16-16
Description: $DESCRIPTION
 This program downloads the true-color cloud image from the FY-4B
 geostationary satellite (NSMC) and sets it as desktop wallpaper.
 It runs as a background scheduler with updates every 15 minutes.
 .
 The wallpaper timeline is stored in ~/.local/share/fy4b/timeline/ and
 automatically falls back to the latest cached image when offline.
EOF

# ---------- 构建 DEB 包 ----------
echo "==> 构建 DEB 包 ..."
dpkg-deb --build "$DEB_DIR"
mv "${DEB_DIR}.deb" "./${APP_NAME}_${VERSION}_${ARCH}.deb"

echo "==> 完成！生成的 DEB 包："
ls -lh "./${APP_NAME}_${VERSION}_${ARCH}.deb"

# 可选：清理临时目录
# rm -rf "$BUILD_DIR" "$DIST_DIR"
