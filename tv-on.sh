#!/bin/bash
export DISPLAY=:0
export XAUTHORITY="/home/$(logname)/.Xauthority"

# Desactivar pantalla portátil, usar solo HDMI a 1080p
xrandr --output LVDS-1 --off --output HDMI-1 --mode 1920x1080 --rate 60 --primary

# Desactivar ahorro de energía
xset s off
xset -dpms
xset s noblank

# Iniciar reproducción si no está corriendo ya
if ! pgrep -f play-videos.sh > /dev/null; then
    /escaparate/play-videos.sh &
fi
