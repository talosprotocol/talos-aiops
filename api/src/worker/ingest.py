import asyncio
import logging
import json
import os
import time
import httpx
from collections import OrderedDict
from typing import Optional, Set

from src.engine.assembler import TraceAssembler

logger = logging.getLogger("aiops-ingest")

class IngestionWorker:
    def __init__(
        self, 
        audit_url: str, 
        assembler: TraceAssembler, 
        cursor_path: str = "/data/cursor.json"
    ):
        self.audit_url = audit_url
        self.assembler = assembler
        self.cursor_path = cursor_path
        self.running = False
        self.current_cursor: Optional[str] = self._load_cursor()
        
        # Idempotency: LRU Set of seen event IDs
        self.seen_events: OrderedDict = OrderedDict()
        self.max_seen_events = 200000

    def _load_cursor(self) -> Optional[str]:
        if not os.path.exists(self.cursor_path):
            return None
        try:
            with open(self.cursor_path, 'r') as f:
                data = json.load(f)
                return data.get("cursor")
        except Exception as e:
            logger.error(f"Failed to load cursor: {e}")
            return None

    def _save_cursor(self, cursor: str):
        try:
            # Atomic write
            tmp_path = f"{self.cursor_path}.tmp"
            with open(tmp_path, 'w') as f:
                json.dump({"cursor": cursor, "updated_at": time.time()}, f)
            os.rename(tmp_path, self.cursor_path)
        except Exception as e:
            logger.error(f"Failed to save cursor: {e}")

    async def start(self):
        self.running = True
        async with httpx.AsyncClient(timeout=10.0) as client:
            while self.running:
                try:
                    await self._poll_cycle(client)
                except Exception as e:
                    logger.error(f"Poll cycle error: {e}")
                    await asyncio.sleep(5) # Backoff on error
                
                await asyncio.sleep(5) # Poll interval

    async def stop(self):
        self.running = False

    async def _poll_cycle(self, client: httpx.AsyncClient):
        # Fetch latest batch (Poll Head)
        # We implicitly ask for the newest items (DESC sort) by NOT sending a cursor.
        params = {"limit": 200}
            
        try:
            resp = await client.get(f"{self.audit_url}/api/events", params=params)
            if resp.status_code == 429:
                logger.warning("Rate limit from Audit Service, backing off.")
                await asyncio.sleep(5)
                return
            resp.raise_for_status()
            
            data = resp.json()
            events = data.get("items", [])
            
            if not events:
                return

            new_events_count = 0
            # Events come in DESC order (newest first). 
            # We process them. Deduplication handles the overlap.
            for event in events:
                eid = event.get("event_id")
                if eid and eid not in self.seen_events:
                    self.seen_events[eid] = True
                    # Maintain LRU size
                    if len(self.seen_events) > self.max_seen_events:
                        self.seen_events.popitem(last=False)
                        
                    self.assembler.process_event(event)
                    new_events_count += 1
            
            if new_events_count > 0:
                logger.info(f"Ingested {new_events_count} new events.")
                
        except httpx.RequestError as e:
            logger.error(f"Network error polling audit service: {e}")
            raise
