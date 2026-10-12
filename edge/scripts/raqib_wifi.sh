#!/usr/bin/env bash
# Keeps the robot reachable anywhere, without a laptop:
#  - known Wi-Fi in range (home, campus, your phone's hotspot) -> join it (internet for the AI)
#  - none found for 60 s -> start the robot's own Wi-Fi "Raqib-Robot" (robot = 10.42.0.1)
#  - while running its own Wi-Fi, every 2 minutes look for a known network again and switch back to it
# Change the name/password in /etc/raqib-wifi.conf (RAQIB_SSID=..., RAQIB_PASS=..., at least 8 characters).
SSID="Raqib-Robot"; PASS="raqib1234"; IFACE="wlan0"
[ -f /etc/raqib-wifi.conf ] && . /etc/raqib-wifi.conf
SSID="${RAQIB_SSID:-$SSID}"; PASS="${RAQIB_PASS:-$PASS}"
command -v nmcli >/dev/null || { echo "NetworkManager (nmcli) not found - Wi-Fi fallback disabled"; sleep infinity; }

connected() { nmcli -t -f DEVICE,STATE,CONNECTION dev 2>/dev/null | grep -q "^${IFACE}:connected:" ; }
on_hotspot() { nmcli -t -f DEVICE,CONNECTION dev 2>/dev/null | grep -q "^${IFACE}:Hotspot$" ; }
known_in_range() {
  nmcli -t -f NAME,TYPE con show 2>/dev/null | awk -F: '$2=="802-11-wireless" && $1!="Hotspot"{print $1}' | while read -r c; do
    ss=$(nmcli -g 802-11-wireless.ssid con show "$c" 2>/dev/null)
    nmcli -t -f SSID dev wifi list --rescan yes 2>/dev/null | grep -Fxq "$ss" && { echo "$c"; break; }
  done
}

waited=0
while true; do
  if connected && ! on_hotspot; then waited=0; sleep 20; continue; fi
  if on_hotspot; then
    sleep 120
    c=$(known_in_range)
    if [ -n "$c" ]; then echo "known network '$c' is back - leaving the robot Wi-Fi"; nmcli con down Hotspot; nmcli con up "$c" || true; fi
    continue
  fi
  waited=$((waited + 10))
  if [ "$waited" -ge 60 ]; then
    echo "no known Wi-Fi - starting the robot's own Wi-Fi '$SSID' (robot address 10.42.0.1)"
    nmcli dev wifi hotspot ifname "$IFACE" con-name Hotspot ssid "$SSID" password "$PASS" || true
    waited=0
  fi
  sleep 10
done
