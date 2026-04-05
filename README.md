# tv_escaparate

Sistema de reproducción de vídeos e imágenes en TV/monitor conectado por HDMI. Reproduce en bucle contenido desde carpetas locales y se controla desde una página web. Funciona de forma autónoma en cualquier equipo Linux con entorno gráfico.

## Características

- Reproducción continua en bucle de vídeos e imágenes
- Intercalado automático de contenido de noticias cada N elementos
- Precarga de archivos en RAM para reproducción sin parpadeos
- Control remoto vía interfaz web (puerto 8080): pausa, skip, subida de archivos, descarga por URL, configuración
- Encendido/apagado automático de la TV por HDMI (Anynet+/CEC) mediante cron
- Refresco automático de la lista de reproducción al detectar cambios en los directorios

## Estructura de directorios

Todo se instala bajo `/escaparate/`:

```
/escaparate/
├── videos/          # Vídeos del bucle principal
├── imagenes/        # Imágenes del bucle principal
├── noticias/        # Contenido intercalado periódicamente
├── ram/             # Tmpfs para precarga en memoria
├── config.json      # Configuración (duración imágenes, frecuencia noticias)
├── play-videos.sh   # Script principal de reproducción
├── player-web.py    # Servidor web de control
├── tv-on.sh         # Activa HDMI e inicia reproducción
└── tv-off.sh        # Detiene reproducción y apaga señal HDMI
```

Formatos soportados:
- **Vídeo:** mp4, mkv, avi, mov, wmv, flv, webm, ts, m4v
- **Imagen:** jpg, jpeg, png, gif, bmp, webp

## Instalación

### Requisitos

- Linux con entorno gráfico (X11)
- mpv, socat, python3

### Instalación automática

```bash
git clone https://github.com/instelest/tv_escaparate
cd tv_escaparate
sudo bash install.sh [usuario]
```

Si no se indica usuario, se usa el que invocó `sudo`. El instalador:

1. Instala dependencias (`mpv`, `socat`, `python3`, `x11-xserver-utils`)
2. Crea `/escaparate/` con los subdirectorios y monta `/escaparate/ram` como tmpfs (2 GB)
3. Copia los scripts y la configuración de mpv
4. Crea e inicia el servicio systemd `player-web` (servidor web en el arranque)
5. Instala los crontabs para encendido automático a las 08:05 y apagado a las 22:00

### Inicio manual

```bash
sudo -u <usuario> DISPLAY=:0 /escaparate/tv-on.sh
```

### Servidor web

El servicio `player-web` arranca automáticamente con el sistema. Para gestionarlo:

```bash
systemctl status player-web
systemctl restart player-web
```

Acceder desde cualquier dispositivo en la misma red: `http://<ip-del-equipo>:8080`

## Configuración

El fichero `/escaparate/config.json` controla:

| Parámetro | Por defecto | Descripción |
|---|---|---|
| `image_duration` | `10` | Segundos que se muestra cada imagen |
| `news_every` | `5` | Cada cuántos elementos del bucle principal se intercala una noticia |

Se puede modificar desde la interfaz web o editando el JSON directamente.

## Horario automático (cron)

| Hora | Acción |
|---|---|
| 07:58 | Reinicio del sistema |
| 08:00 | Activar salida HDMI 1080p@60Hz |
| 08:05 | Encender TV e iniciar reproducción |
| 22:00 | Detener reproducción y apagar señal HDMI |

Los crontabs se encuentran en `crontab-zapatitos.txt` (usuario) y `crontab-root.txt` (root) y se instalan automáticamente con `install.sh`.

## Archivos del repositorio

| Archivo | Descripción |
|---|---|
| `play-videos.sh` | Script principal de reproducción con mpv |
| `player-web.py` | Servidor web de control (puerto 8080) |
| `tv-on.sh` | Activa la salida HDMI e inicia la reproducción |
| `tv-off.sh` | Detiene la reproducción y apaga la señal HDMI |
| `install.sh` | Instalador automático |
| `mpv.conf` | Configuración de mpv (caché, sincronización) |
| `10-noblank.conf` | Configuración X11 para desactivar el apagado de pantalla |
| `crontab-root.txt` | Cron de root: reinicio diario del sistema |
| `crontab-zapatitos.txt` | Cron del usuario: horario de encendido/apagado |
