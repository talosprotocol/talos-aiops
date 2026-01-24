import pytest
import time
from src.engine.assembler import TraceAssembler, Trace

class TestTraceAssembler:

    def test_trace_lifecycle(self):
        assembler = TraceAssembler(max_traces=10, trace_ttl=60)
        
        # 1. New Trace
        event1 = {
            "meta": {"correlation_id": "trace-1"},
            "ts": 1000,
            "event_id": "e1"
        }
        assembler.process_event(event1)
        
        assert "trace-1" in assembler.traces
        assert len(assembler.traces["trace-1"].events) == 1
        
        # 2. Append to Trace
        event2 = {
            "meta": {"correlation_id": "trace-1"},
            "ts": 1001,
            "event_id": "e2"
        }
        assembler.process_event(event2)
        assert len(assembler.traces["trace-1"].events) == 2
        
    def test_fallback_correlation(self):
        assembler = TraceAssembler()
        
        # No correlation_id, use request_id
        event = {
            "request_id": "req-1",
            "ts": 1000,
            "event_id": "e1"
        }
        assembler.process_event(event)
        
        assert "req-1" in assembler.traces
        
    def test_eviction(self):
        assembler = TraceAssembler(max_traces=2)
        
        # Fill capacity
        assembler.process_event({"meta": {"correlation_id": "t1"}, "ts": 1})
        assembler.process_event({"meta": {"correlation_id": "t2"}, "ts": 2})
        
        assert len(assembler.traces) == 2
        
        # Add 3rd, should evict oldest (t1)
        assembler.process_event({"meta": {"correlation_id": "t3"}, "ts": 3})
        
        assert len(assembler.traces) == 2
        assert "t1" not in assembler.traces
        assert "t3" in assembler.traces
        
        # Check eviction queue
        finalized = assembler.get_finalized_batch()
        assert len(finalized) == 1
        assert finalized[0].trace_id == "t1"

    def test_maintenance_expiry(self):
        assembler = TraceAssembler(trace_ttl=0.1) # Short TTL
        
        assembler.process_event({"meta": {"correlation_id": "t1"}})
        
        time.sleep(0.2)
        assembler.maintenance()
        
        assert "t1" not in assembler.traces
        finalized = assembler.get_finalized_batch()
        assert len(finalized) == 1
