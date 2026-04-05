#!/bin/bash
# Reproductor con mpv persistente — sin parpadeos entre archivos

BASE_DIR="/escaparate"
VIDEO_DIR="$BASE_DIR/videos"
IMAGE_DIR="$BASE_DIR/imagenes"
NEWS_DIR="$BASE_DIR/noticias"
STATUS_FILE="/tmp/player-status.json"
MPV_SOCKET="/tmp/mpv-socket"
CONFIG_FILE="$BASE_DIR/config.json"
RAM_DIR="$BASE_DIR/ram"

VIDEO_EXTS=( mp4 mkv avi mov wmv flv webm ts m4v )
IMAGE_EXTS=( jpg jpeg png gif bmp webp )

XUSER=$(who | awk '($2 ~ /^:[0-9]/ || $NF ~ /\(:[0-9]/) {print $1; exit}')
XUSER=${XUSER:-$(logname 2>/dev/null || echo "$SUDO_USER" || whoami)}
export DISPLAY=:0
export XAUTHORITY="/home/${XUSER}/.Xauthority"
export PIPEWIRE_RUNTIME_DIR="/run/user/$(id -u ${XUSER})"
export XDG_RUNTIME_DIR="/run/user/$(id -u ${XUSER})"

# Matar xfdesktop si sigue corriendo y poner fondo negro
# Matar xfdesktop si sigue corriendo y poner fondo negro
pkill -u "$XUSER" xfdesktop 2>/dev/null
sleep 0.3
xrandr --output LVDS-1 --off --output HDMI-1 --mode 1920x1080 --rate 60 --primary
xsetroot -solid black

xset s off
xset -dpms
xset s noblank

# ── Configuración ────────────────────────────────────────────────────
read_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        IMAGE_DURATION=$(python3 -c "
import json
try:
    d=json.load(open('$CONFIG_FILE'))
    print(d.get('image_duration',10))
except:
    print(10)
" 2>/dev/null)
        NEWS_EVERY=$(python3 -c "
import json
try:
    d=json.load(open('$CONFIG_FILE'))
    print(d.get('news_every',5))
except:
    print(5)
" 2>/dev/null)
    else
        IMAGE_DURATION=10
        NEWS_EVERY=5
        echo '{"image_duration":10,"news_every":5}' | tee "$CONFIG_FILE" > /dev/null
    fi
    IMAGE_DURATION=${IMAGE_DURATION:-10}
    NEWS_EVERY=${NEWS_EVERY:-5}
}

# ── Listas de archivos ───────────────────────────────────────────────
get_files() {
    local dir="$1"; shift
    local exts=("$@")
    local args=()
    for ext in "${exts[@]}"; do args+=( -o -iname "*.${ext}" ); done
    unset 'args[0]'
    find "$dir" -type f \( "${args[@]}" \) 2>/dev/null
}

get_main_playlist() {
    { get_files "$VIDEO_DIR" "${VIDEO_EXTS[@]}"; get_files "$IMAGE_DIR" "${IMAGE_EXTS[@]}"; } | shuf
}

get_news_playlist() {
    { get_files "$NEWS_DIR" "${VIDEO_EXTS[@]}"; get_files "$NEWS_DIR" "${IMAGE_EXTS[@]}"; } | shuf
}

dir_mtime() {
    stat -c '%Y' "$VIDEO_DIR" "$IMAGE_DIR" "$NEWS_DIR" 2>/dev/null | md5sum | cut -d' ' -f1
}

is_image() {
    local ext="${1##*.}"
    ext="${ext,,}"
    for e in "${IMAGE_EXTS[@]}"; do [[ "$ext" == "$e" ]] && return 0; done
    return 1
}

# ── IPC con mpv ──────────────────────────────────────────────────────
mpv_send() {
    echo "$1" | socat - UNIX-CONNECT:"$MPV_SOCKET" 2>/dev/null
}

# Espera a que mpv termine de reproducir el archivo actual
wait_playback_end() {
    sleep 0.5
    local tries=0
    while [[ $tries -lt 14400 ]]; do
        sleep 0.5

        # Si el socket desaparece, mpv murió
        if [[ ! -S "$MPV_SOCKET" ]]; then
            return 1
        fi

        local result
        result=$(echo '{"command":["get_property","idle-active"]}' \
            | socat -T2 - UNIX-CONNECT:"$MPV_SOCKET" 2>/dev/null)

        if echo "$result" | grep -q '"data":true'; then
            return 0
        fi

        (( tries++ ))
    done
}

# Arrancar mpv en modo idle (una sola vez, sin cerrar nunca)
start_mpv() {
    rm -f "$RAM_DIR"/* 2>/dev/null
    pkill -u "$XUSER" -f mpv 2>/dev/null
    sleep 0.5
    rm -f "$MPV_SOCKET"

    # Fondo negro mientras mpv arranca
    xsetroot -solid black

    mpv \
        --idle=yes \
        --fullscreen \
        --fs-screen=0 \
        --screen=0 \
        --no-audio \
        --no-osd-bar \
        --no-osc \
        --really-quiet \
        --no-input-default-bindings \
        --stop-screensaver=no \
        --input-ipc-server="$MPV_SOCKET" \
        --background-color="#000000" \
        &

    local tries=0
    while [[ ! -S "$MPV_SOCKET" ]] && [[ $tries -lt 20 ]]; do
        sleep 0.3
        (( tries++ ))
    done
    echo "$(date): mpv iniciado"
}

# Cargar y reproducir un archivo en mpv
play_file() {
    local FILE="$1"
    local fname
    fname=$(basename "$FILE")
    local RAM_FILE="$RAM_DIR/$fname"

    # Copiar a RAM si hay espacio suficiente
    local file_size ram_free
    file_size=$(stat -c '%s' "$FILE" 2>/dev/null || echo 0)
    ram_free=$(df --output=avail -B1 "$RAM_DIR" | tail -1)
    if (( file_size > 0 && file_size < ram_free - 209715200 )); then
        cp "$FILE" "$RAM_FILE" 2>/dev/null && FILE="$RAM_FILE"
    fi

    local FILE_JSON="${FILE//\\/\\\\}"
    FILE_JSON="${FILE_JSON//\"/\\\"}"
    local fname_json="${fname//\"/\\\"}"

    if is_image "$FILE"; then
        read_config
        mpv_send "{\"command\":[\"set_property\",\"image-display-duration\",${IMAGE_DURATION}]}"
        cat > "$STATUS_FILE" <<EOF
{"current":"${fname_json}","updated":"$(date '+%Y-%m-%d %H:%M:%S')","paused":false,"is_image":true}
EOF
    else
        mpv_send '{"command":["set_property","image-display-duration","inf"]}'
        cat > "$STATUS_FILE" <<EOF
{"current":"${fname_json}","updated":"$(date '+%Y-%m-%d %H:%M:%S')","paused":false,"is_image":false}
EOF
    fi

    echo "$(date): ▶ $FILE"
    mpv_send "{\"command\":[\"loadfile\",\"${FILE_JSON}\",\"replace\"]}"
    wait_playback_end

    # Liberar RAM
    rm -f "$RAM_FILE" 2>/dev/null
}

# Reproducir un elemento de noticias
play_news_block() {
    mapfile -t NEWS < <(get_news_playlist)
    [[ ${#NEWS[@]} -eq 0 ]] && return
    local pick="${NEWS[$((RANDOM % ${#NEWS[@]}))]}"
    [[ -f "$pick" ]] && play_file "$pick"
}

# ── Bucle principal ──────────────────────────────────────────────────
read_config
start_mpv

mapfile -t PLAYLIST < <(get_main_playlist)
LAST_MTIME=$(dir_mtime)
ITEM_COUNT=0

while true; do
    read_config

    # Verificar que mpv sigue vivo
    if ! pgrep -u "$XUSER" -x mpv > /dev/null 2>&1; then
        echo "$(date): mpv muerto, reiniciando..."
        start_mpv
    fi

    if [[ ${#PLAYLIST[@]} -eq 0 ]]; then
        echo "{\"current\":\"Sin archivos\",\"updated\":\"$(date '+%Y-%m-%d %H:%M:%S')\",\"paused\":false}" \
            > "$STATUS_FILE"
        sleep 10
        mapfile -t PLAYLIST < <(get_main_playlist)
        LAST_MTIME=$(dir_mtime)
        continue
    fi

    for FILE in "${PLAYLIST[@]}"; do
        [[ -f "$FILE" ]] || continue

        # Intercalar noticias
        if (( ITEM_COUNT > 0 && ITEM_COUNT % NEWS_EVERY == 0 )); then
            play_news_block
        fi

        play_file "$FILE"
        (( ITEM_COUNT++ ))

        # Precargar el siguiente archivo en RAM en paralelo
        NEXT_FILE="${PLAYLIST[$((ITEM_COUNT))]}"
        if [[ -f "$NEXT_FILE" ]]; then
            cp "$NEXT_FILE" "$RAM_DIR/$(basename "$NEXT_FILE")" 2>/dev/null &
        fi

        # Refrescar lista si cambió el directorio
        CURRENT_MTIME=$(dir_mtime)
        if [[ "$CURRENT_MTIME" != "$LAST_MTIME" ]]; then
            echo "$(date): Directorios modificados, refrescando..."
            mapfile -t PLAYLIST < <(get_main_playlist)
            LAST_MTIME="$CURRENT_MTIME"
            break
        fi
    done

    # Al terminar la lista, siempre refresca
    mapfile -t PLAYLIST < <(get_main_playlist)
    LAST_MTIME=$(dir_mtime)
done
