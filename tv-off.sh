#!/bin/bash
export DISPLAY=:0
export XAUTHORITY="/home/$(logname)/.Xauthority"

# Parar mpv y el script de reproducción
pkill -f play-videos.sh
pkill -f mpv
sleep 1

# Mandar señal de apagado a la TV por DPMS (Anynet+ detectará la pérdida de señal)
xset dpms force off
sleep 2

# Apagar salida HDMI (corta la señal, Anynet+ apagará la TV)
HDMI=$(xrandr | awk '/ connected/{print $1}' | grep -i hdmi | head -1)
if [[ -n "$HDMI" ]]; then
    xrandr --output "$HDMI" --off
fi

# Reactivar pantalla del portátil para que el sistema no quede ciego
xrandr --output LVDS-1 --auto
