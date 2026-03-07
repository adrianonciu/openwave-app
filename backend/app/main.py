from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="OpenWave Backend", version="0.1.0")

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok"}