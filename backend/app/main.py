from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.env import load_backend_env

load_backend_env()

from app.api.routes import router
from app.services.tts_service import TtsService


tts_service = TtsService()

app = FastAPI(
    title="OpenWave Backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/audio/generated",
    StaticFiles(directory=tts_service.generated_audio_directory),
    name="generated-audio",
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
