from typing import Dict, List, Deque, Optional
from datetime import datetime
from collections import deque
import time
import logging

logger = logging.getLogger("aiops-assembler")

class Trace:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.events: List[dict] = []
        self.last_updated: float = time.time()
        self.is_finalized: bool = False

    def add(self, event: dict):
        self.events.append(event)
        self.last_updated = time.time()
        # Sort by timestamp to ensure causal ordering within trace
        # We assume 'ts' is ISO string or timestamp number. 
        # For simplicity in v1, we append and sort on finalize if needed, 
        # or rely on upstream partially ordered stream.
        # Strict sort:
        self.events.sort(key=lambda x: (x.get("ts", ""), x.get("event_id", "")))

    def duration(self) -> float:
        if len(self.events) < 2:
            return 0.0
        try:
            # Events are already sorted in self.add()
            start_str = self.events[0].get("ts")
            end_str = self.events[-1].get("ts")
            
            if not start_str or not end_str: return 0.0
            
            # Simple ISO parse
            start = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(end_str).replace("Z", "+00:00"))
            return (end - start).total_seconds()
        except (ValueError, TypeError):
            return 0.0

class TraceAssembler:
    """
    Groups raw audit events into correlated traces.
    Enforces memory bounds and time-based eviction.
    """
    def __init__(self, max_traces: int = 10000, trace_ttl: int = 60):
        self.traces: Dict[str, Trace] = {}
        self.max_traces = max_traces
        self.trace_ttl = trace_ttl
        self.finalized_queue: Deque[Trace] = deque()

    def process_event(self, event: dict):
        """
        Ingest a single event and assign to a trace.
        Correlation Strategy:
        1. 'correlation_id' (Explicit Trace)
        2. 'request_id' (Single Request Scope)
        """
        # 1. Extract Key
        meta = event.get("meta", {})
        trace_id = meta.get("correlation_id") or event.get("correlation_id")
        
        if not trace_id:
            # Fallback to request_id
            trace_id = event.get("request_id")
            
        if not trace_id:
            # Drop or assign to 'unknown' trace? 
            # Dropping un-correlated events for AIOps prevents noise.
            return

        # 2. Assign to Trace
        if trace_id not in self.traces:
            # Eviction check
            if len(self.traces) >= self.max_traces:
                self._evict_oldest()
            self.traces[trace_id] = Trace(trace_id)
            
        trace = self.traces[trace_id]
        trace.add(event)

    def _evict_oldest(self):
        """Force expire the oldest trace (by update time) to free memory."""
        # Simple O(N) scan for now, or use OrderedDict?
        # Python dicts are insertion ordered, but we update keys.
        # Better: Scan once.
        # Optimization: use LRU cache structure if needed.
        if not self.traces:
            return
            
        oldest_id = min(self.traces.keys(), key=lambda k: self.traces[k].last_updated)
        self._finalize(oldest_id)

    def _finalize(self, trace_id: str):
        """Move trace to finalized queue and remove from sorting buffer."""
        if trace_id in self.traces:
            trace = self.traces.pop(trace_id)
            trace.is_finalized = True
            self.finalized_queue.append(trace)

    def maintenance(self):
        """Call periodically to expire idle traces."""
        now = time.time()
        to_finalize = []
        for tid, trace in self.traces.items():
            if now - trace.last_updated > self.trace_ttl:
                to_finalize.append(tid)
        
        for tid in to_finalize:
            self._finalize(tid)

    def get_finalized_batch(self) -> List[Trace]:
        """Retrieve and clear finalized traces for processing."""
        batch = list(self.finalized_queue)
        self.finalized_queue.clear()
        return batch
