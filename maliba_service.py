from __future__ import annotations

import tempfile
from collections import OrderedDict
from pathlib import Path
from threading import Lock, Thread

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from maliba_ai.tts.inference import BambaraTTSInference
from maliba_ai.config.settings import Speakers

app = FastAPI(title="SUTA MALIBA TTS", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_engine = None
_engine_lock = Lock()
_generate_lock = Lock()
_cache_lock = Lock()
_cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()
_cache_max = 64
_warmup_status = {"state": "pending", "error": None}

SPEAKERS = {
    "Bourama": Speakers.Bourama,
    "Adama": Speakers.Adama,
    "Moussa": Speakers.Moussa,
    "Modibo": Speakers.Modibo,
    "Seydou": Speakers.Seydou,
    "Amadou": Speakers.Amadou,
    "Bakary": Speakers.Bakary,
    "Ngolo": Speakers.Ngolo,
    "Ibrahima": Speakers.Ibrahima,
    "Amara": Speakers.Amara,
}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    speaker: str = "Bourama"


def get_engine() -> BambaraTTSInference:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = BambaraTTSInference()
    return _engine


def cache_get(speaker: str, text: str) -> bytes | None:
    key = (speaker, text)
    with _cache_lock:
        value = _cache.get(key)
        if value is not None:
            _cache.move_to_end(key)
        return value


def cache_put(speaker: str, text: str, wav: bytes) -> None:
    key = (speaker, text)
    with _cache_lock:
        _cache[key] = wav
        _cache.move_to_end(key)
        while len(_cache) > _cache_max:
            _cache.popitem(last=False)


def synthesize(text: str, speaker: str) -> bytes:
    cached = cache_get(speaker, text)
    if cached is not None:
        return cached

    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            path = handle.name
        with _generate_lock:
            get_engine().generate_speech(
                text=text,
                speaker_id=SPEAKERS[speaker],
                output_filename=path,
            )
        wav = Path(path).read_bytes()
        cache_put(speaker, text, wav)
        return wav
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


def warmup() -> None:
    _warmup_status["state"] = "warming"
    try:
        synthesize("Aw ni ce.", "Bourama")
        _warmup_status["state"] = "ready"
    except Exception as exc:
        _warmup_status["state"] = "error"
        _warmup_status["error"] = str(exc)


@app.on_event("startup")
def start_warmup() -> None:
    Thread(target=warmup, daemon=True, name="maliba-warmup").start()


@app.get("/health")
def health():
    with _cache_lock:
        cache_entries = len(_cache)
    return {
        "status": "ok",
        "service": "maliba-tts",
        "warmup": _warmup_status["state"],
        "cache_entries": cache_entries,
        "streaming": "sentence-prefetch",
        "speakers": list(SPEAKERS),
    }


@app.post("/v1/tts")
def tts(request: TTSRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Texte vide")
    if request.speaker not in SPEAKERS:
        raise HTTPException(status_code=422, detail="Voix inconnue")

    try:
        wav = synthesize(text, request.speaker)
        return Response(
            content=wav,
            media_type="audio/wav",
            headers={"Content-Disposition": 'inline; filename="suta-maliba.wav"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Echec MALIBA: {exc}") from exc


@app.get("/", response_class=HTMLResponse)
def ui():
    return """<!doctype html>
<html lang='fr'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>MALIBA - Voix bambara</title>
<style>
body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;background:#faf8f2;color:#17211b}
.card{background:white;border:1px solid #e5e1d7;border-radius:18px;padding:22px;box-shadow:0 8px 30px #0000000d}
textarea,select,button{width:100%;box-sizing:border-box;margin-top:10px;font:inherit}
textarea,select{padding:12px;border:1px solid #ccc;border-radius:10px}
button{padding:13px;border:0;border-radius:10px;background:#173f2c;color:white;font-weight:700;cursor:pointer}
button:disabled{opacity:.55;cursor:not-allowed}
audio{width:100%;margin-top:18px}.muted{color:#667268;font-size:.95rem}
.badge{display:inline-block;padding:4px 9px;border-radius:999px;background:#edf4ef;color:#173f2c;font-size:.8rem;font-weight:700;margin-bottom:12px}
</style>
</head>
<body>
<h1>MALIBA - Voix bambara</h1>
<div class='card'>
<div class='badge'>Lecture progressive SUTA</div>
<label>Texte bambara</label>
<textarea id='text' rows='5'>Aw ni ce. I ka kɛnɛ wa? SUTA bɛ an dɛmɛ ka kunnafoniw sɔrɔ an ka kan na.</textarea>
<label>Voix</label>
<select id='speaker'>
<option>Bourama</option><option>Adama</option><option>Moussa</option><option>Modibo</option><option>Seydou</option><option>Amadou</option><option>Bakary</option><option>Ngolo</option><option>Ibrahima</option><option>Amara</option>
</select>
<button id='go' disabled>Preparation de MALIBA...</button>
<p id='status' class='muted'>Chargement du modele en arriere-plan...</p>
<audio id='audio' controls></audio>
</div>
<script>
const go=document.getElementById('go'),status=document.getElementById('status'),audio=document.getElementById('audio');
async function checkReady(){
 try{
  const r=await fetch('/health'); const h=await r.json();
  if(h.warmup==='ready'){
   go.disabled=false; go.textContent='Parler'; status.textContent='MALIBA est pret.'; return;
  }
  if(h.warmup==='error'){
   go.disabled=false; go.textContent='Parler'; status.textContent='Warm-up incomplet, essai direct possible.'; return;
  }
  status.textContent='Preparation de MALIBA...';
 }catch(e){status.textContent='Verification du service...'}
 setTimeout(checkReady,2000);
}
checkReady();

function splitText(text){
 const parts=text.match(/[^.!?。！？]+[.!?。！？]?/g)||[text];
 return parts.map(x=>x.trim()).filter(Boolean);
}

async function fetchChunk(text,speaker){
 const r=await fetch('/v1/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,speaker})});
 if(!r.ok){let m='Erreur MALIBA';try{m=(await r.json()).detail||m}catch{}throw new Error(m)}
 return await r.blob();
}

function playBlob(blob){
 return new Promise((resolve,reject)=>{
  const url=URL.createObjectURL(blob);
  audio.src=url;
  audio.onended=()=>{URL.revokeObjectURL(url);resolve();};
  audio.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('Lecture audio impossible'));};
  audio.play().catch(reject);
 });
}

go.onclick=async()=>{
 const chunks=splitText(document.getElementById('text').value);
 const speaker=document.getElementById('speaker').value;
 if(!chunks.length)return;
 go.disabled=true;
 const started=performance.now();
 try{
  status.textContent='Preparation de la premiere phrase...';
  let nextPromise=fetchChunk(chunks[0],speaker);
  for(let i=0;i<chunks.length;i++){
   const blob=await nextPromise;
   const firstMs=Math.round(performance.now()-started);
   if(i+1<chunks.length) nextPromise=fetchChunk(chunks[i+1],speaker);
   status.textContent=i===0 ? `La voix demarre apres ${firstMs/1000}s - suite en preparation...` : `Lecture ${i+1}/${chunks.length}...`;
   await playBlob(blob);
  }
  status.textContent='Termine.';
 }catch(e){
  status.textContent='Erreur : '+e.message;
 }finally{
  go.disabled=false;
 }
};
</script>
</body>
</html>"""
