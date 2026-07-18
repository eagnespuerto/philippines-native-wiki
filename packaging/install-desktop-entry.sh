#!/usr/bin/env bash
# Install the "Philippines Native Wiki" launcher into the current user's
# desktop environment. Menu entry appears under Science / Education
# (LXDE, XFCE, GNOME, KDE all honour these Categories).
#
# Usage:  ./packaging/install-desktop-entry.sh
#         ./packaging/install-desktop-entry.sh --uninstall

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE="${SCRIPT_DIR}/philippines-native-wiki.desktop"

TARGET_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
TARGET="${TARGET_DIR}/philippines-native-wiki.desktop"

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -f "${TARGET}"
  echo "Removed ${TARGET}"
  command -v update-desktop-database >/dev/null 2>&1 \
    && update-desktop-database "${TARGET_DIR}" || true
  exit 0
fi

mkdir -p "${TARGET_DIR}"
sed "s|__APP_DIR__|${APP_DIR}|g" "${TEMPLATE}" > "${TARGET}"
chmod 644 "${TARGET}"

echo "Installed ${TARGET}"
echo "  Exec: python3 ${APP_DIR}/app/main.py"
echo "  Menu: Science > Philippines Native Wiki"

command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "${TARGET_DIR}" || true

# LXDE (default on 32-bit Raspberry Pi OS) reads the menu on next login
# but respects an lxpanelctl reload for immediate effect.
command -v lxpanelctl >/dev/null 2>&1 && lxpanelctl restart || true
