from __future__ import annotations

import tempfile
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from maliba_ai.tts.inference import BambaraTTSInference
from maliba_ai.config.settings import Speakers

app = FastAPI(title="SUTA MALIBA TTS", version="0.1.0")
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


@app.get("/health")
def health():
    return {"status": "ok", "service": "maliba-tts", "speakers": list(SPEAKERS)}


@app.post("/v1/tts")
def tts(request: TTSRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Texte vide")
    if request.speaker not in SPEAKERS:
        raise HTTPException(status_code=422, detail="Voix inconnue")

    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            path = handle.name

        with _generate_lock:
            get_engine().generate_speech(
                text=text,
                speaker_id=SPEAKERS[request.speaker],
                output_filename=path,
            )

        wav = Path(path).read_bytes()
        return Response(
            content=wav,
            media_type="audio/wav",
            headers={"Content-Disposition": 'inline; filename="suta-maliba.wav"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Echec MALIBA: {exc}") from exc
    finally:
        if path:
            Path(path).unlink(missing_ok=True)


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
audio{width:100%;margin-top:18px}.muted{color:#667268;font-size:.95rem}
</style>
</head>
<body>
<h1>MALIBA - Voix bambara</h1>
<div class='card'>
<label>Texte bambara</label>
<textarea id='text' rows='5'>Aw ni ce. I ka kɛnɛ wa?</textarea>
<label>Voix</label>
<select id='speaker'>
<option>Bourama</option><option>Adama</option><option>Moussa</option><option>Modibo</option><option>Seydou</option><option>Amadou</option><option>Bakary</option><option>Ngolo</option><option>Ibrahima</option><option>Amara</option>
</select>
<button id='go'>Generer la voix</button>
<p id='status' class='muted'>Pret.</p>
<audio id='audio' controls></audio>
</div>
<script>
const go=document.getElementById('go'),status=document.getElementById('status'),audio=document.getElementById('audio');
go.onclick=async()=>{
 go.disabled=true; status.textContent='Generation en cours...';
 try{
  const r=await fetch('/v1/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:document.getElementById('text').value,speaker:document.getElementById('speaker').value})});
  if(!r.ok){let m='Erreur MALIBA';try{m=(await r.json()).detail||m}catch{}throw new Error(m)}
  const blob=await r.blob(); audio.src=URL.createObjectURL(blob); await audio.play(); status.textContent='Termine.';
 }catch(e){status.textContent='Erreur : '+e.message}finally{go.disabled=false}
};
</script>
</body>
</html>"""
