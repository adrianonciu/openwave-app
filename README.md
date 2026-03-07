# OpenWave

AI audio-first news briefing app.

Stack:
- Flutter
- FastAPI
- AI summarization
- TTS
## Local backend run

cd backend
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn pydantic
uvicorn app.main:app --reload

Open:
http://127.0.0.1:8000/docs