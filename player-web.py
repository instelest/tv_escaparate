#!/usr/bin/env python3
import http.server
import json
import os
import subprocess
import urllib.parse
import mimetypes
import threading
import uuid
import socket as _socket

STATUS_FILE  = "/tmp/player-status.json"
CONFIG_FILE  = "/home/zapatitos/player-config.json"
VIDEO_DIR    = "/srv/samba/shared/Videos"
IMAGE_DIR    = "/srv/samba/shared/Imagenes"
NEWS_DIR     = "/srv/samba/shared/Noticias"
PORT         = 8080
MPV_SOCKET   = "/tmp/mpv-socket"
XUSER        = "zapatitos"

VIDEO_EXTS = {'.mp4','.mkv','.avi','.mov','.wmv','.flv','.webm','.ts','.m4v'}
IMAGE_EXTS = {'.jpg','.jpeg','.png','.gif','.bmp','.webp'}
ALL_EXTS   = VIDEO_EXTS | IMAGE_EXTS

downloads      = {}
downloads_lock = threading.Lock()

DEFAULT_CONFIG = {"image_duration": 10, "news_every": 5}

def read_config():
    try:
        return json.loads(open(CONFIG_FILE).read())
    except Exception:
        return dict(DEFAULT_CONFIG)

def write_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

def list_dir(path):
    try:
        return sorted([f for f in os.listdir(path)
                       if os.path.splitext(f)[1].lower() in ALL_EXTS])
    except Exception:
        return []

# ── HTML ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Monitor de Reproducción</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#0f0f0f;color:#e0e0e0;min-height:100vh;padding:20px}
h1{text-align:center;font-size:1.6em;color:#fff;margin-bottom:20px;letter-spacing:1px}

/* Tabs */
.tabs{display:flex;gap:4px;max-width:1200px;margin:0 auto 20px;border-bottom:2px solid #222}
.tab{padding:10px 24px;cursor:pointer;font-size:.85em;text-transform:uppercase;letter-spacing:1px;
     color:#666;border-radius:6px 6px 0 0;border:none;background:none;transition:all .2s}
.tab:hover{color:#aaa;background:#1a1a1a}
.tab.active{color:#e94560;background:#1a1a1a;border-bottom:2px solid #e94560;margin-bottom:-2px}
.tab-panel{display:none;max-width:1200px;margin:0 auto}
.tab-panel.active{display:block}

/* Grid */
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
.card{background:#1a1a1a;border-radius:10px;padding:20px;border:1px solid #2a2a2a}
.card-title{font-size:.75em;text-transform:uppercase;letter-spacing:2px;color:#888;margin-bottom:14px}

/* Now playing */
.now-playing{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #0f3460;border-left:4px solid #e94560}
.now-playing .card-title{color:#e94560}
.now-title{font-size:1.2em;font-weight:bold;color:#fff;word-break:break-word}
.now-updated{font-size:.72em;color:#555;margin-top:6px}
.now-section{font-size:.75em;color:#7eb8ff;margin-top:4px}
.pulse{display:inline-block;width:10px;height:10px;background:#e94560;border-radius:50%;
       margin-right:8px;animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.8)}}

/* Controles */
.controls{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}
.ctrl-btn{background:#0f3460;color:#fff;border:none;border-radius:6px;padding:8px 16px;
          font-size:1em;cursor:pointer;transition:background .2s}
.ctrl-btn:hover{background:#1a4a80}
.ctrl-btn.btn-stop{background:#3a1a1a;color:#e94560}
.ctrl-btn.btn-stop:hover{background:#5a2a2a}
.ctrl-btn.active{background:#e94560}

/* Config */
.config-row{display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.config-label{font-size:.85em;color:#aaa;min-width:180px}
.config-input{background:#111;border:1px solid #333;color:#e0e0e0;padding:6px 10px;
              border-radius:6px;font-size:.85em;width:80px;outline:none}
.config-input:focus{border-color:#e94560}
.config-btn{background:#0f3460;color:#fff;border:none;border-radius:6px;padding:6px 16px;
            cursor:pointer;font-size:.82em}
.config-btn:hover{background:#1a4a80}
.config-saved{color:#4caf50;font-size:.78em;margin-left:8px;opacity:0;transition:opacity .3s}
.config-saved.show{opacity:1}

/* Playlist */
.playlist{max-height:320px;overflow-y:auto}
.playlist::-webkit-scrollbar{width:4px}
.playlist::-webkit-scrollbar-thumb{background:#333;border-radius:2px}
.pl-item{display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid #222;
         font-size:.84em;transition:background .15s}
.pl-item:last-child{border-bottom:none}
.pl-item:hover{background:#252525}
.pl-item.active{background:#1a1a2e;color:#fff;font-weight:bold}
.pl-item .icon{font-size:.8em;color:#444;flex-shrink:0}
.pl-item.active .icon{color:#e94560}
.pl-item .name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pl-item .ftype{font-size:.7em;color:#555;flex-shrink:0;padding:1px 5px;background:#222;border-radius:3px}
.pl-item .actions{display:flex;gap:4px;flex-shrink:0}
.btn-sm{padding:3px 7px;border-radius:4px;font-size:.74em;border:none;cursor:pointer;transition:opacity .2s}
.btn-sm:hover{opacity:.8}
.btn-stream{background:#0f3460;color:#7eb8ff}
.btn-del{background:#3a1a1a;color:#e94560}
.btn-rename{background:#2a2a1a;color:#ffd700}
.count-badge{display:inline-block;background:#2a2a2a;color:#888;border-radius:10px;
             padding:1px 10px;font-size:.74em;margin-left:6px}

/* Upload */
.drop-zone{border:2px dashed #333;border-radius:8px;padding:24px;text-align:center;
           color:#555;cursor:pointer;transition:border-color .2s,color .2s;position:relative}
.drop-zone.dragover{border-color:#e94560;color:#e94560}
.drop-zone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%}
.drop-icon{font-size:1.8em;margin-bottom:6px}
.drop-text{font-size:.83em}
.progress-bar-wrap{margin-top:10px;background:#2a2a2a;border-radius:4px;overflow:hidden;display:none;height:6px}
.progress-bar{height:100%;background:#e94560;width:0;transition:width .3s}
.upload-status{font-size:.77em;margin-top:6px;min-height:16px;color:#888}

/* Stream */
.stream-player{display:none;flex-direction:column;gap:10px}
.stream-player.visible{display:flex}
.stream-title{font-size:.84em;color:#aaa;word-break:break-word}
video{width:100%;border-radius:6px;background:#000;max-height:280px}
.btn-close-stream{align-self:flex-end;padding:4px 12px;background:#2a2a2a;color:#888;
                  border:none;border-radius:4px;cursor:pointer;font-size:.8em}

/* YouTube */
.yt-row{display:flex;gap:8px;margin-bottom:10px}
.yt-input{flex:1;background:#111;border:1px solid #333;color:#e0e0e0;padding:8px 12px;
          border-radius:6px;font-size:.84em;outline:none}
.yt-input:focus{border-color:#e94560}
.yt-btn{background:#e94560;color:#fff;border:none;border-radius:6px;padding:8px 14px;
        cursor:pointer;font-size:.84em;font-weight:bold;white-space:nowrap}
.yt-btn:disabled{opacity:.5;cursor:not-allowed}
.dl-list{max-height:140px;overflow-y:auto}
.dl-item{padding:7px 10px;border-bottom:1px solid #222;font-size:.79em}
.dl-item:last-child{border-bottom:none}
.dl-name{color:#aaa;margin-bottom:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.dl-bar-wrap{background:#2a2a2a;border-radius:3px;height:4px;margin-bottom:3px}
.dl-bar{height:100%;border-radius:3px;background:#e94560;transition:width .5s}
.dl-status{color:#666;font-size:.74em}
.dl-status.done{color:#4caf50}
.dl-status.error{color:#e94560}

/* Toast */
#toast{position:fixed;bottom:24px;right:24px;background:#1a1a2e;border:1px solid #0f3460;
       color:#fff;padding:12px 20px;border-radius:8px;font-size:.84em;opacity:0;
       transition:opacity .3s;pointer-events:none;z-index:999}
#toast.show{opacity:1}
.section-badge{display:inline-block;font-size:.7em;padding:2px 8px;border-radius:10px;
               margin-left:8px;vertical-align:middle}
.badge-videos{background:#0f3460;color:#7eb8ff}
.badge-imagenes{background:#1a2e1a;color:#4caf50}
.badge-noticias{background:#2e1a0f;color:#ff9800}
</style>
</head>
<body>
<h1>📺 Monitor de Reproducción</h1>

<!-- TABS -->
<div class="tabs">
    <button class="tab active" onclick="showTab('monitor')">📊 Monitor</button>
    <button class="tab" onclick="showTab('videos')">🎬 Videos</button>
    <button class="tab" onclick="showTab('imagenes')">🖼️ Imágenes</button>
    <button class="tab" onclick="showTab('noticias')">📰 Noticias</button>
</div>

<!-- TAB: MONITOR -->
<div class="tab-panel active" id="tab-monitor">
    <div class="grid">
        <div class="card now-playing">
            <div class="card-title"><span class="pulse"></span>Reproduciendo ahora</div>
            <div class="now-title" id="current">Cargando...</div>
            <div class="now-section" id="current-section"></div>
            <div class="now-updated" id="updated"></div>
            <div class="controls">
                <button class="ctrl-btn" id="btnPlay"  onclick="playerCmd('play')"  title="Reproducir">▶</button>
                <button class="ctrl-btn" id="btnPause" onclick="togglePause()"      title="Pausar/Reanudar">⏸</button>
                <button class="ctrl-btn" id="btnNext"  onclick="playerCmd('next')"  title="Siguiente">⏭</button>
                <button class="ctrl-btn btn-stop"      onclick="playerCmd('stop')"  title="Detener">⏹</button>
            </div>
        </div>
        <div class="card">
            <div class="card-title">⚙️ Configuración</div>
            <div class="config-row">
                <span class="config-label">⏱ Duración imagen (seg)</span>
                <input class="config-input" type="number" id="cfgImgDur" min="1" max="300" value="10">
            </div>
            <div class="config-row">
                <span class="config-label">📰 Noticias cada N elementos</span>
                <input class="config-input" type="number" id="cfgNewsEvery" min="1" max="100" value="5">
            </div>
            <button class="config-btn" onclick="saveConfig()">💾 Guardar configuración</button>
            <span class="config-saved" id="configSaved">✓ Guardado</span>
        </div>
        <div class="card" style="grid-column:span 2">
            <div class="card-title">
                Reproducción general
                <span class="count-badge" id="totalCount">0</span>
                <span class="section-badge badge-videos" id="videoCount">0 videos</span>
                <span class="section-badge badge-imagenes" id="imageCount">0 imágenes</span>
                <span class="section-badge badge-noticias" id="newsCount">0 noticias</span>
            </div>
            <div class="playlist" id="playlist-monitor"></div>
        </div>
    </div>
</div>

<!-- TAB: VIDEOS -->
<div class="tab-panel" id="tab-videos">
    <div class="grid">
        <div class="card">
            <div class="card-title">📤 Subir video</div>
            <div class="drop-zone" id="dropZone-videos">
                <input type="file" id="fileInput-videos" accept="video/*" multiple>
                <div class="drop-icon">🎬</div>
                <div class="drop-text">Arrastra o haz clic<br><small>mp4, mkv, avi, mov, wmv, webm…</small></div>
            </div>
            <div class="progress-bar-wrap" id="progressWrap-videos"><div class="progress-bar" id="progressBar-videos"></div></div>
            <div class="upload-status" id="uploadStatus-videos"></div>
        </div>
        <div class="card">
            <div class="card-title">▶ Descargar YouTube y otros / URL </div>
            <div class="yt-row">
                <input class="yt-input" id="ytUrl" type="text" placeholder="https://www.youtube.com/watch?v=...">
                <button class="yt-btn" id="ytBtn" onclick="startDownload()">Descargar</button>
            </div>
            <div class="dl-list" id="dlList"><div data-empty style="color:#444;font-size:.8em;padding:8px 0">Las descargas aparecerán aquí</div></div>
        </div>
        <div class="card" style="grid-column:span 2">
            <div class="card-title">Lista de videos <span class="count-badge" id="count-videos">0</span></div>
            <div class="playlist" id="playlist-videos"></div>
        </div>
    </div>
</div>

<!-- TAB: IMAGENES -->
<div class="tab-panel" id="tab-imagenes">
    <div class="grid">
        <div class="card" style="grid-column:span 2">
            <div class="card-title">📤 Subir imagen</div>
            <div class="drop-zone" id="dropZone-imagenes">
                <input type="file" id="fileInput-imagenes" accept="image/*" multiple>
                <div class="drop-icon">🖼️</div>
                <div class="drop-text">Arrastra o haz clic<br><small>jpg, png, gif, webp, bmp…</small></div>
            </div>
            <div class="progress-bar-wrap" id="progressWrap-imagenes"><div class="progress-bar" id="progressBar-imagenes"></div></div>
            <div class="upload-status" id="uploadStatus-imagenes"></div>
        </div>
        <div class="card" style="grid-column:span 2">
            <div class="card-title">Lista de imágenes <span class="count-badge" id="count-imagenes">0</span></div>
            <div class="playlist" id="playlist-imagenes"></div>
        </div>
    </div>
</div>

<!-- TAB: NOTICIAS -->
<div class="tab-panel" id="tab-noticias">
    <div class="grid">
        <div class="card" style="grid-column:span 2">
            <div class="card-title">📤 Subir noticia (video o imagen)</div>
            <div class="drop-zone" id="dropZone-noticias">
                <input type="file" id="fileInput-noticias" accept="video/*,image/*" multiple>
                <div class="drop-icon">📰</div>
                <div class="drop-text">Arrastra o haz clic<br><small>Videos e imágenes para intercalar como noticias</small></div>
            </div>
            <div class="progress-bar-wrap" id="progressWrap-noticias"><div class="progress-bar" id="progressBar-noticias"></div></div>
            <div class="upload-status" id="uploadStatus-noticias"></div>
        </div>
        <div class="card" style="grid-column:span 2">
            <div class="card-title">Lista de noticias <span class="count-badge" id="count-noticias">0</span></div>
            <div class="playlist" id="playlist-noticias"></div>
        </div>
    </div>
</div>

<!-- STREAM player flotante -->
<div class="card" id="streamCard" style="max-width:1200px;margin:20px auto;display:none">
    <div class="card-title">🎥 Streaming
        <button class="btn-close-stream" onclick="closeStream()" style="float:right">✕ Cerrar</button>
    </div>
    <div class="stream-title" id="streamTitle"></div>
    <video id="videoEl" controls autoplay style="margin-top:10px;width:100%;border-radius:6px;background:#000;max-height:500px;display:none"></video>
    <img id="imageEl" style="margin-top:10px;width:100%;border-radius:6px;max-height:500px;object-fit:contain;display:none">
</div>


<div id="toast"></div>

<script>
let currentVideo='', isPaused=false;
const SECTIONS={
    videos:{dir:'videos',accept:'video/*'},
    imagenes:{dir:'imagenes',accept:'image/*'},
    noticias:{dir:'noticias',accept:'video/*,image/*'}
};

// ── Tabs ────────────────────────────────────────────────────────────
function showTab(name){
    document.querySelectorAll('.tab,.tab-panel').forEach(el=>{
        el.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach((t,i)=>{
        if(['monitor','videos','imagenes','noticias'][i]===name) t.classList.add('active');
    });
    document.getElementById('tab-'+name).classList.add('active');
    if(name!=='monitor') refreshSection(name);
}

// ── Toast ───────────────────────────────────────────────────────────
function toast(msg,err=false){
    const t=document.getElementById('toast');
    t.textContent=msg;
    t.style.borderColor=err?'#e94560':'#0f3460';
    t.classList.add('show');
    setTimeout(()=>t.classList.remove('show'),3000);
}

// ── Monitor refresh ─────────────────────────────────────────────────
async function refresh(){
    try{
        const d=await fetch('/status').then(r=>r.json());
        currentVideo=d.current||'';
        isPaused=d.paused||false;
        document.getElementById('current').textContent=currentVideo||(d.running?'—':'⏹ Detenido');
        document.getElementById('updated').textContent=d.updated?'Actualizado: '+d.updated:'';

        // Badge de sección
        const secEl=document.getElementById('current-section');
        if(d.section){
            const labels={videos:'🎬 Videos',imagenes:'🖼️ Imágenes',noticias:'📰 Noticias'};
            secEl.textContent=labels[d.section]||d.section;
        } else { secEl.textContent=''; }

        document.getElementById('btnPause').textContent=isPaused?'▶ Reanudar':'⏸ Pausar';
        document.getElementById('btnPause').classList.toggle('active',isPaused);
        document.getElementById('btnPlay').classList.toggle('active',d.running&&!isPaused);

        // Contadores
        const vids=(d.playlists?.videos||[]);
        const imgs=(d.playlists?.imagenes||[]);
        const news=(d.playlists?.noticias||[]);
        document.getElementById('videoCount').textContent=vids.length+' videos';
        document.getElementById('imageCount').textContent=imgs.length+' imágenes';
        document.getElementById('newsCount').textContent=news.length+' noticias';
        document.getElementById('totalCount').textContent=vids.length+imgs.length;

        // Playlist combinada en monitor
        buildPlaylist('monitor', [...vids.map(n=>({name:n,section:'videos'})),
                                   ...imgs.map(n=>({name:n,section:'imagenes'}))],
                      currentVideo, true);

        // Cargar config
        if(d.config){
            document.getElementById('cfgImgDur').value=d.config.image_duration||10;
            document.getElementById('cfgNewsEvery').value=d.config.news_every||5;
        }
    }catch(e){}
}
refresh();
setInterval(refresh,5000);

// ── Refresh sección individual ──────────────────────────────────────
async function refreshSection(section){
    try{
        const d=await fetch('/list/'+section).then(r=>r.json());
        document.getElementById('count-'+section).textContent=d.files.length;
        buildPlaylist(section, d.files.map(n=>({name:n,section})), currentVideo, false);
    }catch(e){}
}

// ── Construir lista ─────────────────────────────────────────────────
function buildPlaylist(id, items, active, showSection){
    const list=document.getElementById('playlist-'+id);
    if(!list) return;
    const scroll=list.scrollTop;
    list.innerHTML='';
    if(!items.length){
        list.innerHTML='<div style="color:#444;padding:12px;font-size:.85em">No hay archivos</div>';
        return;
    }
    const IMAGE_E=['.jpg','.jpeg','.png','.gif','.bmp','.webp'];
    items.forEach(({name,section})=>{
        const isImg=IMAGE_E.includes(name.substring(name.lastIndexOf('.')).toLowerCase());
        const div=document.createElement('div');
        div.className='pl-item'+(name===active?' active':'');

        const icon=document.createElement('span');
        icon.className='icon';
        icon.textContent=name===active?'▶':'○';

        const span=document.createElement('span');
        span.className='name'; span.textContent=name; span.title=name;

        const ftype=document.createElement('span');
        ftype.className='ftype';
        ftype.textContent=isImg?'IMG':'VID';

        const acts=document.createElement('div');
        acts.className='actions';

        const bs=document.createElement('button');
        bs.className='btn-sm btn-stream'; bs.textContent='▶'; bs.title='Streaming';
        bs.onclick=e=>{e.stopPropagation();streamFile(name,section);};

        const br=document.createElement('button');
        br.className='btn-sm btn-rename'; br.textContent='✏️'; br.title='Renombrar';
        br.onclick=e=>{e.stopPropagation();renameFile(name,section);};

        const bd=document.createElement('button');
        bd.className='btn-sm btn-del'; bd.textContent='🗑'; bd.title='Eliminar';
        bd.onclick=e=>{e.stopPropagation();deleteFile(name,section);};

        acts.appendChild(bs); acts.appendChild(br); acts.appendChild(bd);
        div.appendChild(icon); div.appendChild(span); div.appendChild(ftype);
        if(showSection){
            const sb=document.createElement('span');
            sb.className='section-badge badge-'+section;
            sb.textContent=section;
            div.appendChild(sb);
        }
        div.appendChild(acts);
        list.appendChild(div);
    });
    list.scrollTop=scroll;
}

// ── Controles ───────────────────────────────────────────────────────
async function playerCmd(action){
    await fetch('/player/'+action,{method:'POST'});
    setTimeout(refresh,600);
    const msgs={play:'▶ Reproduciendo',next:'⏭ Siguiente',stop:'⏹ Detenido'};
    toast(msgs[action]||action);
}
async function togglePause(){
    const action=isPaused?'resume':'pause';
    await fetch('/player/'+action,{method:'POST'});
    isPaused=!isPaused;
    document.getElementById('btnPause').textContent=isPaused?'▶ Reanudar':'⏸ Pausar';
    document.getElementById('btnPause').classList.toggle('active',isPaused);
    toast(isPaused?'⏸ Pausado':'▶ Reanudado');
}

// ── Config ──────────────────────────────────────────────────────────
async function saveConfig(){
    const cfg={
        image_duration:parseInt(document.getElementById('cfgImgDur').value)||10,
        news_every:parseInt(document.getElementById('cfgNewsEvery').value)||5
    };
    const r=await fetch('/config',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)}).then(r=>r.json());
    if(r.ok){
        const el=document.getElementById('configSaved');
        el.classList.add('show');
        setTimeout(()=>el.classList.remove('show'),2000);
        toast('Configuración guardada');
    } else toast('Error guardando config',true);
}

// ── Stream ───────────────────────────────────────────────────────────
function streamFile(name, section){
    const vid  = document.getElementById('videoEl');
    const img  = document.getElementById('imageEl');
    const card = document.getElementById('streamCard');
    const IMAGE_E=['.jpg','.jpeg','.png','.gif','.bmp','.webp'];
    const isImg = IMAGE_E.includes(name.substring(name.lastIndexOf('.')).toLowerCase());
    const url = '/stream/' + section + '/' + encodeURIComponent(name);

    document.getElementById('streamTitle').textContent = '▶ ' + name;
    card.style.display = 'block';

    if(isImg){
        vid.style.display = 'none';
        vid.pause(); vid.src = '';
        img.style.display = 'block';
        img.src = url;
    } else {
        img.style.display = 'none';
        img.src = '';
        vid.style.display = 'block';
        vid.src = url;
        vid.play();
    }
    toast('Cargando: ' + name);
    card.scrollIntoView({behavior:'smooth'});
}

function closeStream(){
    const vid = document.getElementById('videoEl');
    const img = document.getElementById('imageEl');
    vid.pause(); vid.src = ''; vid.style.display = 'none';
    img.src = ''; img.style.display = 'none';
    document.getElementById('streamCard').style.display = 'none';
}

// ── Delete ───────────────────────────────────────────────────────────
async function deleteFile(name,section){
    if(!confirm('¿Eliminar "'+name+'"?\nEsta acción no se puede deshacer.')) return;
    const r=await fetch('/delete/'+section+'/'+encodeURIComponent(name),
        {method:'DELETE'}).then(r=>r.json());
    if(r.ok){ toast('Eliminado: '+name); refresh(); refreshSection(section); }
    else toast('Error: '+(r.error||'?'),true);
}

// ── Rename ───────────────────────────────────────────────────────────
async function renameFile(name,section){
    const ext=name.lastIndexOf('.');
    const suggested=ext>0?name.substring(0,ext):name;
    const newName=prompt('Nuevo nombre:\n'+name,suggested);
    if(!newName||newName.trim()===''||newName.trim()===suggested) return;
    const r=await fetch('/rename/'+section,{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({old:name,new:newName.trim()})}).then(r=>r.json());
    if(r.ok){ toast('Renombrado: '+r.new); refresh(); refreshSection(section); }
    else toast('Error: '+(r.error||'?'),true);
}

// ── Upload ───────────────────────────────────────────────────────────
['videos','imagenes','noticias'].forEach(section=>{
    const dz=document.getElementById('dropZone-'+section);
    const fi=document.getElementById('fileInput-'+section);
    dz.addEventListener('dragover',e=>{e.preventDefault();dz.classList.add('dragover');});
    dz.addEventListener('dragleave',()=>dz.classList.remove('dragover'));
    dz.addEventListener('drop',e=>{e.preventDefault();dz.classList.remove('dragover');uploadFiles(e.dataTransfer.files,section);});
    fi.addEventListener('change',()=>uploadFiles(fi.files,section));
});

async function uploadFiles(files,section){
    for(const f of files) await uploadOne(f,section);
    document.getElementById('fileInput-'+section).value='';
    refresh(); refreshSection(section);
}
function uploadOne(file,section){
    return new Promise(resolve=>{
        const xhr=new XMLHttpRequest();
        const pw=document.getElementById('progressWrap-'+section);
        const pb=document.getElementById('progressBar-'+section);
        const us=document.getElementById('uploadStatus-'+section);
        pw.style.display='block'; pb.style.width='0%';
        us.textContent='Subiendo: '+file.name;
        xhr.upload.onprogress=e=>{
            if(e.lengthComputable){
                const p=Math.round(e.loaded/e.total*100);
                pb.style.width=p+'%';
                us.textContent='Subiendo: '+file.name+' ('+p+'%)';
            }
        };
        xhr.onload=()=>{
            try{
                const d=JSON.parse(xhr.responseText);
                if(d.ok){us.textContent='✓ '+file.name;toast('Subido: '+file.name);}
                else{us.textContent='✗ '+(d.error||'?');toast('Error subiendo',true);}
            }catch{us.textContent='✗ Error';}
            pb.style.width='100%';
            setTimeout(()=>{pw.style.display='none';},1500);
            resolve();
        };
        xhr.onerror=()=>{us.textContent='✗ Error de red';resolve();};
        const fd=new FormData(); fd.append('file',file);
        xhr.open('POST','/upload/'+section); xhr.send(fd);
    });
}

// ── YouTube ──────────────────────────────────────────────────────────
async function startDownload(){
    const input=document.getElementById('ytUrl');
    const btn=document.getElementById('ytBtn');
    const url=input.value.trim();
    if(!url) return;
    input.value=''; btn.disabled=true; btn.textContent='...';
    try{
        const r=await fetch('/yt-download',{method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({url})}).then(r=>r.json());
        if(r.ok){toast('Descarga iniciada');trackDownload(r.id,url);}
        else toast('Error: '+(r.error||'?'),true);
    }catch(e){toast('Error de red',true);}
    btn.disabled=false; btn.textContent='Descargar';
}
function trackDownload(id,url){
    const dlList=document.getElementById('dlList');
    if(dlList.querySelector('[data-empty]')) dlList.innerHTML='';
    const item=document.createElement('div');
    item.className='dl-item';
    item.innerHTML=`<div class="dl-name" title="${url}">${url}</div>
        <div class="dl-bar-wrap"><div class="dl-bar" id="dlbar-${id}" style="width:0%"></div></div>
        <div class="dl-status" id="dlst-${id}">Iniciando...</div>`;
    dlList.prepend(item);
    const iv=setInterval(async()=>{
        try{
            const d=await fetch('/yt-status/'+id).then(r=>r.json());
            const bar=document.getElementById('dlbar-'+id);
            const st=document.getElementById('dlst-'+id);
            const nm=item.querySelector('.dl-name');
            if(d.filename) nm.textContent=d.filename;
            if(bar) bar.style.width=(d.percent||0)+'%';
            if(st) st.textContent=d.status||'...';
            if(d.done){
                st.className='dl-status done';
                st.textContent='✓ '+(d.filename||'Completado');
                if(bar) bar.style.width='100%';
                clearInterval(iv); refresh(); refreshSection('videos');
                toast('Descargado: '+(d.filename||''));
            }
            if(d.error){
                st.className='dl-status error'; st.textContent='✗ '+d.error;
                clearInterval(iv); toast('Error en descarga',true);
            }
        }catch{clearInterval(iv);}
    },2000);
}
document.getElementById('ytUrl').addEventListener('keydown',e=>{if(e.key==='Enter')startDownload();});
</script>
</body>
</html>"""


# ── Helpers ───────────────────────────────────────────────────────────
def get_dir(section):
    return {
        'videos':   VIDEO_DIR,
        'imagenes': IMAGE_DIR,
        'noticias': NEWS_DIR,
    }.get(section)

def list_section(section):
    d = get_dir(section)
    if not d:
        return []
    return sorted([f for f in os.listdir(d)
                   if os.path.splitext(f)[1].lower() in ALL_EXTS])

def detect_section(filename):
    """Detecta en qué carpeta está el archivo actual."""
    for s, d in [('videos', VIDEO_DIR), ('imagenes', IMAGE_DIR), ('noticias', NEWS_DIR)]:
        if os.path.isfile(os.path.join(d, filename)):
            return s
    return ''

def mpv_cmd(cmd):
    try:
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(MPV_SOCKET)
        sock.sendall((json.dumps(cmd) + '\n').encode())
        sock.close()
    except Exception:
        pass

def update_status_paused(paused):
    try:
        data = json.loads(open(STATUS_FILE).read())
        data['paused'] = paused
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass


# ── Handler ────────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        p = self.path.split('?')[0]

        if p == '/':
            self._html(HTML)

        elif p == '/status':
            try:
                data = json.loads(open(STATUS_FILE).read())
            except Exception:
                data = {'current': 'Sin datos', 'updated': '', 'paused': False}
            # Playlists desde directorio real
            data['playlists'] = {
                'videos':   list_section('videos'),
                'imagenes': list_section('imagenes'),
                'noticias': list_section('noticias'),
            }
            # Detectar sección del archivo actual
            if data.get('current'):
                data['section'] = detect_section(data['current'])
            data['running'] = (subprocess.run(
                ['pgrep', '-f', 'play-videos.sh'],
                capture_output=True).returncode == 0)
            data['config'] = read_config()
            self._json(data)

        elif p.startswith('/list/'):
            section = p[6:]
            self._json({'files': list_section(section)})

        elif p.startswith('/stream/'):
            # /stream/<section>/<filename>
            parts = p[8:].split('/', 1)
            if len(parts) == 2:
                section, name = parts[0], urllib.parse.unquote(parts[1])
            else:
                section, name = 'videos', urllib.parse.unquote(parts[0])
            name = os.path.basename(name)
            d = get_dir(section) or VIDEO_DIR
            path = os.path.join(d, name)
            if not os.path.isfile(path):
                self._err(404, 'No encontrado')
                return
            self._stream_file(path)

        elif p.startswith('/yt-status/'):
            dl_id = p[11:]
            with downloads_lock:
                info = dict(downloads.get(dl_id, {'error': 'No encontrado'}))
            self._json(info)

        else:
            self._err(404, 'Not found')

    def do_DELETE(self):
        p = self.path
        if p.startswith('/delete/'):
            parts = p[8:].split('/', 1)
            if len(parts) == 2:
                section, name = parts[0], urllib.parse.unquote(parts[1])
            else:
                section, name = 'videos', urllib.parse.unquote(parts[0])
            name = os.path.basename(name)
            d = get_dir(section)
            if not d:
                self._json({'ok': False, 'error': 'Sección inválida'})
                return
            path = os.path.join(d, name)
            try:
                os.remove(path)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
        else:
            self._err(404, 'Not found')

    def do_POST(self):
        p = self.path

        if p.startswith('/upload/'):
            section = p[8:]
            self._handle_upload(section)

        elif p.startswith('/rename/'):
            section = p[8:]
            self._handle_rename(section)

        elif p == '/config':
            self._handle_config()

        elif p == '/yt-download':
            self._handle_yt_download()

        elif p == '/player/pause':
            mpv_cmd({"command": ["set_property", "pause", True]})
            update_status_paused(True)
            self._json({'ok': True})

        elif p == '/player/resume':
            mpv_cmd({"command": ["set_property", "pause", False]})
            update_status_paused(False)
            self._json({'ok': True})

        elif p == '/player/next':
            mpv_cmd({"command": ["stop"]})
            self._json({'ok': True})

        elif p == '/player/stop':
            subprocess.run(['pkill', '-u', XUSER, '-f', 'play-videos.sh'])
            subprocess.run(['pkill', '-u', XUSER, '-f', 'mpv'])
            try:
                data = json.loads(open(STATUS_FILE).read())
                data.update({'current': 'Detenido', 'paused': False, 'running': False})
                with open(STATUS_FILE, 'w') as f:
                    json.dump(data, f)
            except Exception:
                pass
            self._json({'ok': True})

        elif p == '/player/play':
            if subprocess.run(['pgrep', '-f', 'play-videos.sh'],
                              capture_output=True).returncode != 0:
                subprocess.Popen(
                    ['/usr/local/bin/play-videos.sh'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    user=XUSER
                )
            self._json({'ok': True})

        else:
            self._err(404, 'Not found')

    # ── Upload ─────────────────────────────────────────────────────────
    def _handle_upload(self, section):
        d = get_dir(section)
        if not d:
            self._json({'ok': False, 'error': 'Sección inválida'})
            return
        try:
            content_type = self.headers.get('Content-Type', '')
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part.split('=', 1)[1].strip()
                    break
            if not boundary:
                self._json({'ok': False, 'error': 'Sin boundary'})
                return
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            sep = ('--' + boundary).encode()
            parts = body.split(sep)
            filename = None
            file_data = None
            for part in parts:
                if b'Content-Disposition' not in part:
                    continue
                if b'\r\n\r\n' in part:
                    hr, content = part.split(b'\r\n\r\n', 1)
                elif b'\n\n' in part:
                    hr, content = part.split(b'\n\n', 1)
                else:
                    continue
                hs = hr.decode('utf-8', errors='replace')
                for line in hs.splitlines():
                    if 'Content-Disposition' in line and 'filename=' in line:
                        for seg in line.split(';'):
                            seg = seg.strip()
                            if seg.startswith('filename='):
                                filename = seg.split('=', 1)[1].strip().strip('"')
                if filename:
                    if content.endswith(b'\r\n'):
                        content = content[:-2]
                    file_data = content
                    break
            if not filename or file_data is None:
                self._json({'ok': False, 'error': 'No se recibió archivo'})
                return
            filename = os.path.basename(filename)
            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALL_EXTS:
                self._json({'ok': False, 'error': 'Formato no permitido: ' + ext})
                return
            dest = os.path.join(d, filename)
            with open(dest, 'wb') as f:
                f.write(file_data)
            self._json({'ok': True, 'filename': filename})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)})

    # ── Rename ─────────────────────────────────────────────────────────
    def _handle_rename(self, section):
        d = get_dir(section)
        if not d:
            self._json({'ok': False, 'error': 'Sección inválida'})
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            old = os.path.basename(body.get('old', ''))
            new = os.path.basename(body.get('new', ''))
            if not old or not new:
                self._json({'ok': False, 'error': 'Nombre vacío'})
                return
            old_ext = os.path.splitext(old)[1].lower()
            new_ext = os.path.splitext(new)[1].lower()
            if not new_ext:
                new = new + old_ext
            src = os.path.join(d, old)
            dst = os.path.join(d, new)
            if not os.path.isfile(src):
                self._json({'ok': False, 'error': 'Archivo no encontrado'})
                return
            if os.path.exists(dst):
                self._json({'ok': False, 'error': 'Ya existe un archivo con ese nombre'})
                return
            os.rename(src, dst)
            self._json({'ok': True, 'new': new})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)})

    # ── Config ─────────────────────────────────────────────────────────
    def _handle_config(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            cfg = read_config()
            if 'image_duration' in body:
                cfg['image_duration'] = max(1, int(body['image_duration']))
            if 'news_every' in body:
                cfg['news_every'] = max(1, int(body['news_every']))
            write_config(cfg)
            self._json({'ok': True})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)})

    # ── YouTube ────────────────────────────────────────────────────────
    def _handle_yt_download(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            url = body.get('url', '').strip()
            if not url:
                self._json({'ok': False, 'error': 'URL vacía'})
                return
            dl_id = str(uuid.uuid4())[:8]
            with downloads_lock:
                downloads[dl_id] = {'status': 'Iniciando...', 'percent': 0,
                                    'done': False, 'filename': ''}
            t = threading.Thread(target=self._do_download, args=(dl_id, url), daemon=True)
            t.start()
            self._json({'ok': True, 'id': dl_id})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)})

    def _do_download(self, dl_id, url):
        try:
            output_tmpl = os.path.join(VIDEO_DIR, '%(title)s.%(ext)s')
            result = subprocess.run(
                ['/usr/local/bin/yt-dlp', '--get-filename',
                 '-f', 'bestvideo+bestaudio/best',
                 '--merge-output-format', 'mp4', '-o', output_tmpl, url],
                capture_output=True, text=True
            )
            if result.stdout.strip():
                expected = os.path.basename(result.stdout.strip().splitlines()[-1])
                if expected:
                    with downloads_lock:
                        downloads[dl_id]['filename'] = expected
            cmd = [
                '/usr/local/bin/yt-dlp', '--no-playlist',
                '-f', 'bestvideo+bestaudio/best',
                '--merge-output-format', 'mp4', '--no-part',
                '-o', output_tmpl, '--newline', url
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                line = line.strip()
                if '[download]' in line and '%' in line:
                    try:
                        pct = float(line.split('%')[0].split()[-1])
                        with downloads_lock:
                            downloads[dl_id]['percent'] = pct
                            downloads[dl_id]['status'] = f'Descargando {pct:.1f}%'
                    except Exception:
                        pass
                for marker in ['Merging formats into', 'Destination:', '[download] Destination:']:
                    if marker in line:
                        try:
                            fname = os.path.basename(line.split(marker)[-1].strip().strip('"'))
                            if fname:
                                with downloads_lock:
                                    downloads[dl_id]['filename'] = fname
                        except Exception:
                            pass
            proc.wait()
            if proc.returncode == 0:
                if not downloads[dl_id].get('filename'):
                    try:
                        files = [f for f in os.listdir(VIDEO_DIR)
                                 if os.path.splitext(f)[1].lower() in VIDEO_EXTS]
                        if files:
                            newest = max(files, key=lambda f: os.path.getmtime(
                                os.path.join(VIDEO_DIR, f)))
                            with downloads_lock:
                                downloads[dl_id]['filename'] = newest
                    except Exception:
                        pass
                with downloads_lock:
                    downloads[dl_id]['done'] = True
                    downloads[dl_id]['percent'] = 100
                    downloads[dl_id]['status'] = 'Completado'
            else:
                with downloads_lock:
                    downloads[dl_id]['error'] = 'yt-dlp terminó con error'
        except Exception as e:
            with downloads_lock:
                downloads[dl_id]['error'] = str(e)

    # ── Stream con Range ───────────────────────────────────────────────
    def _stream_file(self, path):
        size = os.path.getsize(path)
        mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
        rh = self.headers.get('Range')
        if rh:
            try:
                start, end = rh.replace('bytes=', '').split('-')
                start = int(start)
                end = int(end) if end else size - 1
            except Exception:
                start, end = 0, size - 1
            length = end - start + 1
            self.send_response(206)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Content-Length', str(length))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            with open(path, 'rb') as f:
                f.seek(start)
                remaining = length
                while remaining:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        else:
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(size))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)

    # ── Utils ──────────────────────────────────────────────────────────
    def _html(self, content):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode())

    def _json(self, obj):
        self._json_raw(json.dumps(obj))

    def _json_raw(self, raw):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(raw.encode())

    def _err(self, code, msg):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(msg.encode())

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    print(f'Monitor en http://0.0.0.0:{PORT}')
    http.server.HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
