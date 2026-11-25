#!/usr/bin/env bash
# ============================================================
#  build_deb.sh — dong goi GoVoice Studio thanh file cai .deb
#    bash studio/packaging/build_deb.sh
#    sudo apt install ./dist/govoice-studio_<ver>_all.deb
#  Sau khi cai: tim "GoVoice Studio" trong menu ung dung, hoac go `govoice-studio`.
#
#  Goi chi chua APP (cua so + backend + giao dien, vai tram KB). No dung GoVoice va
#  ROS da co tren may: duong dan trong ~/.config/govoice-studio/settings.json
#  (mac dinh ~/Documents/Go2_assitant, /opt/ros/lyrical, ~/ros2_ws).
# ============================================================
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"          # studio/
ROOT="$(dirname "$HERE")"
VER=$(python3 -c "import re;print(re.search(r'VERSION = \"([^\"]+)\"', open('$HERE/server.py').read()).group(1))")
PKG=govoice-studio
OUT="$ROOT/dist"
B=$(mktemp -d)
trap 'rm -rf "$B"' EXIT

mkdir -p "$B/DEBIAN" "$B/opt/$PKG/web" "$B/usr/bin" "$B/usr/share/applications" \
         "$B/usr/share/icons/hicolor/scalable/apps" "$B/usr/share/icons/hicolor/256x256/apps"
cp "$HERE/govoice_studio.py" "$HERE/server.py" "$B/opt/$PKG/"
cp "$HERE"/web/* "$B/opt/$PKG/web/"
cp "$HERE/web/icon.svg" "$B/usr/share/icons/hicolor/scalable/apps/$PKG.svg"
/usr/bin/python3 - "$HERE/web/icon.svg" "$B/usr/share/icons/hicolor/256x256/apps/$PKG.png" <<'PY' || echo "  (bo qua icon PNG)"
import sys, gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf
GdkPixbuf.Pixbuf.new_from_file_at_size(sys.argv[1], 256, 256).savev(sys.argv[2], "png", [], [])
PY

cat > "$B/usr/bin/$PKG" <<SH
#!/bin/sh
exec /usr/bin/python3 /opt/$PKG/govoice_studio.py "\$@"
SH
chmod 755 "$B/usr/bin/$PKG"

cat > "$B/usr/share/applications/$PKG.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=GoVoice Studio
GenericName=Robot Control Station
Comment=Điều khiển Go2 bằng giọng nói — mô phỏng và robot thật
Exec=$PKG
Icon=$PKG
Terminal=false
Categories=Development;Science;Robotics;
Keywords=robot;go2;ros;voice;unitree;
StartupWMClass=govoice-studio
DESK

SIZE=$(du -sk "$B/opt" "$B/usr" | awk '{s+=$1} END {print s}')
cat > "$B/DEBIAN/control" <<CTL
Package: $PKG
Version: $VER
Section: science
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
Recommends: python3-psutil
Maintainer: GoVoice <noreply@localhost>
Description: GoVoice Studio - voice control station for Unitree Go2
 Desktop app for the GoVoice assistant: live map built by the robot
 (LiDAR + D435i), fleet cards, typed and spoken Vietnamese commands,
 E-STOP, and one-click start of the Gazebo simulation and the local LLM.
 Uses the system WebKitGTK (no bundled browser).
CTL
cat > "$B/DEBIAN/postinst" <<'POST'
#!/bin/sh
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q /usr/share/icons/hicolor || true
exit 0
POST
chmod 755 "$B/DEBIAN/postinst"

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$B" "$OUT/${PKG}_${VER}_all.deb" >/dev/null
ls -la "$OUT/${PKG}_${VER}_all.deb"
echo "Cai:  sudo apt install $OUT/${PKG}_${VER}_all.deb"
