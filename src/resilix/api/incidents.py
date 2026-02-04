from __future__ import annotations

from fastapi import APIRouter, HTTPException

from resilix.services.session import get_session_store

router = APIRouter()


@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str) -> dict:
    store = get_session_store()
    state = await store.get(incident_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"incident_id": incident_id, "state": state}
