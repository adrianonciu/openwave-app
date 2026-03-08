Continuăm proiectul OpenWave.

Repo local:
D:\aplicatie_telefon\openwave-app

Repo GitHub:
adrianonciu/openwave-app

Lucrez cu Codex Local, nu Cloud.

Înainte de orice modificare, citește și respectă:
- docs/PROJECT_MAP_v2.md
- docs/AGENTS_v2.md
- docs/ARCHITECTURE.md
- docs/TASKS.md
- docs/DAILY_LOG.md

Structura repo trebuie păstrată strict:
- backend/
- flutter_app/
- docs/

Nu crea:
- mobile/
- frontend/
- client/
- app/

Stack:
- Backend: FastAPI
- Frontend: Flutter
- Audio: flutter_tts

Status actual:

Backend:
- RSS ingestion funcțional
- ArticleService
- SegmentService
- BriefingService
- endpoint /briefing/today funcțional

Flutter:
- HomeScreen încarcă Daily Brief din backend
- PlayerScreen implementează audio briefing player

PlayerScreen suportă deja:
- TTS playback
- auto-start briefing
- intro audio dinamic
- durată totală estimată în intro
- auto-play între articole
- voice cue între articole ("Next story")
- playlist interactiv
- highlight pentru articolul activ
- progress bar
- current / total / remaining playback time
- durată estimată pentru articolul curent
- durată estimată în playlist

Pipeline actual:
RSS
→ Article
→ Segment
→ DailyBrief
→ Flutter Player
→ TTS playback

Reguli de lucru:
- taskuri mici
- modifică minimum necesar
- nu refactoriza inutil
- nu instala dependențe fără motiv
- nu rula serverul
- nu rula teste
- arată diff-ul complet
- oprește-te după diff
- commit după fiecare task

Reguli suplimentare importante:
- nu spune "1 file changed" dacă ai modificat mai multe fișiere
- dacă introduci dependențe noi, spune explicit
- dacă modifici fișiere de platformă (AndroidManifest, iOS plist etc.), spune explicit
- dacă un task cere modificarea unui singur fișier, nu modifica altele fără motiv clar
- preferă îmbunătățiri sigure și incrementale în locul schimbărilor mari

Obiectivul sesiunii curente:
[SCRIE AICI TASKUL CURENT]
