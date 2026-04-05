#!/bin/bash
# Instalador de tv_escaparate
# Uso: sudo bash install.sh [usuario]
# Si no se indica usuario, se usa el que invocó sudo o el usuario actual.

set -e

BASE_DIR="/escaparate"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Verificar root ────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "Ejecuta con sudo: sudo bash install.sh [usuario]"
    exit 1
fi

# ── Detectar usuario ──────────────────────────────────────────────────
TARGET_USER="${1:-${SUDO_USER:-$(logname 2>/dev/null || whoami)}}"
if [[ -z "$TARGET_USER" || "$TARGET_USER" == "root" ]]; then
    echo "Error: no se pudo determinar el usuario. Pásalo como argumento:"
    echo "  sudo bash install.sh nombre_usuario"
    exit 1
fi

if ! id "$TARGET_USER" &>/dev/null; then
    echo "Error: el usuario '$TARGET_USER' no existe."
    exit 1
fi

echo "=== Instalando tv_escaparate ==="
echo "  Directorio base : $BASE_DIR"
echo "  Usuario         : $TARGET_USER"
echo ""

# ── Dependencias ──────────────────────────────────────────────────────
echo "[1/5] Instalando dependencias..."
apt-get install -y mpv socat python3 x11-xserver-utils > /dev/null

# yt-dlp (opcional, para descarga de vídeos desde URL)
if ! command -v yt-dlp &>/dev/null; then
    if command -v pip3 &>/dev/null; then
        pip3 install --quiet yt-dlp
    else
        echo "  (yt-dlp no instalado — pip3 no disponible; instálalo manualmente si lo necesitas)"
    fi
fi

# ── Crear estructura de directorios ──────────────────────────────────
echo "[2/5] Creando directorios en $BASE_DIR..."
mkdir -p "$BASE_DIR"/{videos,imagenes,noticias,ram}
chown -R "$TARGET_USER":"$TARGET_USER" "$BASE_DIR"
chmod -R 755 "$BASE_DIR"

# Montar ram como tmpfs (2 GB) si no está ya en fstab
if ! grep -q "$BASE_DIR/ram" /etc/fstab; then
    echo "tmpfs $BASE_DIR/ram tmpfs defaults,size=2G 0 0" >> /etc/fstab
    mount "$BASE_DIR/ram" 2>/dev/null || true
fi

# ── Copiar scripts ────────────────────────────────────────────────────
echo "[3/5] Copiando scripts a $BASE_DIR..."
for f in play-videos.sh tv-on.sh tv-off.sh; do
    cp "$SCRIPT_DIR/$f" "$BASE_DIR/$f"
    chmod +x "$BASE_DIR/$f"
done
cp "$SCRIPT_DIR/player-web.py" "$BASE_DIR/player-web.py"

# Configuración de mpv
MPV_CONF_DIR="/home/$TARGET_USER/.config/mpv"
mkdir -p "$MPV_CONF_DIR"
cp "$SCRIPT_DIR/mpv.conf" "$MPV_CONF_DIR/mpv.conf"
chown -R "$TARGET_USER":"$TARGET_USER" "$MPV_CONF_DIR"

# Desactivar apagado de pantalla (X11)
if [[ -d /etc/X11/xorg.conf.d ]]; then
    cp "$SCRIPT_DIR/10-noblank.conf" /etc/X11/xorg.conf.d/10-noblank.conf
fi

# Fichero de configuración inicial
CONFIG_FILE="$BASE_DIR/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo '{"image_duration":10,"news_every":5}' > "$CONFIG_FILE"
    chown "$TARGET_USER":"$TARGET_USER" "$CONFIG_FILE"
fi

# ── Servicio systemd para el servidor web ────────────────────────────
echo "[4/5] Creando servicio systemd (player-web)..."
cat > /etc/systemd/system/player-web.service <<EOF
[Unit]
Description=tv_escaparate - servidor web de control
After=network.target

[Service]
User=$TARGET_USER
ExecStart=/usr/bin/python3 $BASE_DIR/player-web.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable player-web.service
systemctl restart player-web.service

# ── Crontab del usuario ───────────────────────────────────────────────
echo "[5/5] Instalando crontab del usuario $TARGET_USER..."
CRON_TMP=$(mktemp)
sed "s|\$HOME|/home/$TARGET_USER|g" "$SCRIPT_DIR/crontab-zapatitos.txt" > "$CRON_TMP"
crontab -u "$TARGET_USER" "$CRON_TMP"
rm -f "$CRON_TMP"

# Crontab de root (reinicio diario)
crontab -u root "$SCRIPT_DIR/crontab-root.txt"

# ── Listo ─────────────────────────────────────────────────────────────
echo ""
echo "=== Instalación completada ==="
echo ""
echo "  Directorios de contenido:"
echo "    Vídeos    : $BASE_DIR/videos"
echo "    Imágenes  : $BASE_DIR/imagenes"
echo "    Noticias  : $BASE_DIR/noticias"
echo ""
echo "  Interfaz web  : http://$(hostname -I | awk '{print $1}'):8080"
echo ""
echo "  Para iniciar la reproducción manualmente:"
echo "    sudo -u $TARGET_USER DISPLAY=:0 $BASE_DIR/tv-on.sh"
echo ""
echo "  Estado del servicio web:"
echo "    systemctl status player-web"
