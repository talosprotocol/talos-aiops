from fastapi import FastAPI
from contextlib import asynccontextmanager
import os
import asyncio
import logging
from datetime import datetime, timezone
import uuid
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from pydantic import BaseModel

from src.engine.assembler import TraceAssembler
from src.engine.markov import TransitionMatrixEngine
from src.worker.ingest import IngestionWorker

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("aiops-main")

# Metrics
AIOPS_INTEGRITY_SCORE = Gauge("aiops_integrity_score", "System integrity score based on anomaly rate")
AIOPS_MODEL_READY = Gauge("aiops_model_ready", "Whether the anomaly model is trained and ready")
AIOPS_TRACES_TRACKED = Gauge("aiops_traces_tracked", "Number of currently active traces")

# State
assembler = TraceAssembler(max_traces=10000)
engine = TransitionMatrixEngine(alpha=0.5)
worker = None

# Scoring History for Integrity Calculation
SCORE_HISTORY = []
MAX_HISTORY = 100

# Job Tracking for Demo
JOBS = {}

class TriggerRequest(BaseModel):
    action: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    audit_url = os.getenv("AUDIT_SERVICE_URL", "http://talos-audit-service:8001")
    global worker
    worker = IngestionWorker(audit_url, assembler, cursor_path="/data/cursor.json")
    
    # Start Worker
    logger.info(f"Starting AIOps Ingestion Worker targeting {audit_url}")
    ingest_task = asyncio.create_task(worker.start())
    
    # Start Maintenance/Scoring Loop
    score_task = asyncio.create_task(background_scoring_loop())
    
    yield
    
    # Shutdown
    logger.info("Shutting down AIOps...")
    await worker.stop()
    ingest_task.cancel()
    score_task.cancel()
    try:
        await ingest_task
        await score_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Talos AIOps", lifespan=lifespan)

async def background_scoring_loop():
    """Periodically finalize traces and update the model."""
    while True:
        try:
            # 1. Maintenance (timeouts)
            assembler.maintenance()
            AIOPS_TRACES_TRACKED.set(len(assembler.traces))
            
            # 2. Process Finalized Traces
            traces = assembler.get_finalized_batch()
            for trace in traces:
                # Score BEFORE learning (for anomaly detection)
                score = engine.score_trace(trace.events)
                SCORE_HISTORY.append(score)
                if len(SCORE_HISTORY) > MAX_HISTORY:
                    SCORE_HISTORY.pop(0)
                
                engine.add_trace(trace.events)
                
                # Check for expiration
                if engine.total_traces > 2000: # Window size hardcap v1
                    engine.expire_oldest()
                    
            # 3. Update Metrics
            ready = engine.total_traces > 100 # Simple readiness threshold
            AIOPS_MODEL_READY.set(1 if ready else 0)
            
            # Calculate Integrity Score (Real Logic)
            current_integrity = 1.0
            if SCORE_HISTORY:
                avg_score = sum(SCORE_HISTORY) / len(SCORE_HISTORY)
                current_integrity = 1.0 / (1.0 + avg_score)
            
            AIOPS_INTEGRITY_SCORE.set(current_integrity)
            
        except Exception as e:
            logger.error(f"Scoring loop error: {e}")
            
        await asyncio.sleep(5)

@app.get("/v1/status")
async def get_v1_status():
    """V1 status endpoint for dashboard parity."""
    ready = engine.total_traces > 100
    score = 1.0
    try:
        score = AIOPS_INTEGRITY_SCORE.collect()[0].samples[0].value
    except (IndexError, AttributeError):
        pass
        
    return {
        "status": "ready" if ready else "training",
        "model_ready": ready,
        "integrity_score": score,
        "active_traces": len(assembler.traces)
    }

@app.post("/v1/trigger")
async def trigger_job(req: TriggerRequest):
    """Trigger a mock DevOps job for demonstration."""
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    
    status = "queued"
    if req.action == "deny_demo":
        status = "denied"
    elif req.action == "plan_deploy_verify":
        status = "completed"
        
    job = {
        "job_id": job_id,
        "status": status,
        "action": req.action,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    JOBS[job_id] = job
    
    return job

@app.get("/v1/logs")
async def get_logs(limit: int = 200):
    """Return recent system logs."""
    # Mock logs for demo
    return [
        f"[{datetime.now(timezone.utc).isoformat()}] INFO: Ingestion worker processed batch",
        f"[{datetime.now(timezone.utc).isoformat()}] INFO: Anomaly model updated (traces={engine.total_traces})",
    ]

@app.get("/health")
async def health():
    return {"status": "ok", "service": "aiops", "model_ready": engine.total_traces > 100}

@app.get("/metrics/integrity")
async def integrity_metrics():
    """Operational metrics for the anomaly detection engine."""
    ready = engine.total_traces > 100
    score = 1.0
    try:
        score = AIOPS_INTEGRITY_SCORE.collect()[0].samples[0].value
    except (IndexError, AttributeError):
        pass

    return {
        "model_ready": ready,
        "readiness_reason": "ok" if ready else f"insufficient_data ({engine.total_traces}/100 traces)",
        "training_window_traces": engine.total_traces,
        "integrity_score": score,
        "recent_anomaly_scores_avg": sum(SCORE_HISTORY)/len(SCORE_HISTORY) if SCORE_HISTORY else 0.0,
        "stats": {
            "states": len(engine.states),
            "edges": len(engine.edge_counts),
            "active_traces": len(assembler.traces)
        }
    }

@app.get("/metrics")
async def prometheus_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
