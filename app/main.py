from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db, SessionLocal
from .services.auth_service import create_default_admin, get_session_user
from .routes.admin import router as admin_router
from .routes.appointments import router as appointments_router
from .routes.availabilities import router as availabilities_router
from .routes.otp import router as otp_router
from .routes.patients import router as patients_router
from .routes.results import router as results_router
from .routes.messages import router as messages_router
from .routes.twilio import router as twilio_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise l'application au démarrage (création de l'admin par défaut)."""
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()
        
    from .services.reminders import start_doctor_reminder_scheduler
    start_doctor_reminder_scheduler()
    
    yield


app = FastAPI(title="Cid API", lifespan=lifespan)
app.include_router(admin_router)
app.include_router(availabilities_router)
app.include_router(appointments_router)
app.include_router(otp_router)
app.include_router(patients_router)
app.include_router(results_router)
app.include_router(messages_router)
app.include_router(twilio_router)


from fastapi.responses import RedirectResponse, FileResponse
import os

@app.get("/logo.jpeg")
def get_logo():
    logo_path = os.path.join(os.path.dirname(__file__), "..", "ok.jpeg")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    return {"error": "Logo not found"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root(request: Request, db: Session = Depends(get_db)):
    user = get_session_user(request, db)
    if user:
        return RedirectResponse(url="/admin")
    return RedirectResponse(url="/admin/login")

