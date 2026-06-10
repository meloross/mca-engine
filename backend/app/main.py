from __future__ import annotations

from fastapi import FastAPI

from app.api.admin import router as admin_router
from app.api.dashboard import router as dashboard_router
from app.api.exports import router as exports_router
from app.api.form_leads import router as form_leads_router
from app.api.signals import router as signals_router

app = FastAPI(title="MCA Legal Signal Engine")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(admin_router)
app.include_router(signals_router)
app.include_router(form_leads_router)
app.include_router(exports_router)
app.include_router(dashboard_router)
