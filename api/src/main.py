from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal, Optional
import os
import hashlib
import json
import base64

app = FastAPI(title="Talos DevOps Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from Env
MODE = os.getenv("EXAMPLES_MODE", "released")
SDK_VERSION = "0.1.0" # Mock for now, should read from pkg
PROTOCOL_RANGE = "1.0-2.0"
CONTRACT_HASH = "mock_contract_hash" 

class TriggerRequest(BaseModel):
    action: Literal["plan_deploy_verify", "deny_demo", "status_only"]

class TriggerResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "denied"]
    message: Optional[str] = None

@app.get("/health")
async def health():
    return {
        "app": "talos-aiops",
        "app_version": "0.1.0",
        "mode": MODE,
        "sdk_version": SDK_VERSION,
        "protocol_range": PROTOCOL_RANGE,
        "contract_hash": CONTRACT_HASH,
        "schedule_hash": None # Not a ratchet app
    }

@app.get("/v1/status")
async def status():
    return {"status": "idle", "active_jobs": 0}

@app.get("/v1/logs")
async def logs(limit: int = 200):
    # Mock logs for now
    return [
        {"timestamp": "2026-01-04T12:00:00Z", "level": "INFO", "message": "Agent initialized"},
        {"timestamp": "2026-01-04T12:00:01Z", "level": "INFO", "message": f"Mode: {MODE}"}
    ]

@app.post("/v1/trigger", response_model=TriggerResponse)
async def trigger(req: TriggerRequest):
    if req.action == "deny_demo":
        return TriggerResponse(job_id="job_123", status="denied", message="Action denied by Talos Policy")
    
    return TriggerResponse(job_id="job_456", status="queued", message=f"Queued action: {req.action}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8200)
