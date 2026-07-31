#!/bin/sh
# govoice-mic-setup.sh — dat gain thu mic USB GoVoice = 35% MOI KHI CAM VAO.
#
# Ly do: so card ALSA cua mic doi moi lan rut-cam (0/1/2...), va gain phan cung
# hay reset. Script nay tim card USB theo TEN (dong 'USB-Audio' trong
# /proc/asound/cards) roi ep gain ve 35% -> lan cam nao cung giong het.
#
# Duoc goi tu udev rule /etc/udev/rules.d/99-govoice-mic.rules khi cam mic.
sleep 1                                   # doi sound card enumerate xong
CARD=$(awk '/USB-Audio/{print $1; exit}' /proc/asound/cards)
[ -z "$CARD" ] && exit 0
for CTL in Mic Capture; do
    if amixer -c "$CARD" sset "$CTL" 35% unmute >/dev/null 2>&1; then
        break
    fi
done
exit 0
