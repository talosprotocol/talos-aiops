import pytest
from src.engine.markov import TransitionMatrixEngine

class TestMarkovEngine:
    
    def test_state_extraction(self):
        engine = TransitionMatrixEngine()
        
        events = [
            {"principal": {"type": "user"}, "action": "login", "outcome": "OK"},
            {"principal": {"type": "user"}, "action": "view_dashboard", "outcome": "OK"},
        ]
        
        seq = engine._extract_sequence(events)
        assert seq == ["user:login:OK", "user:view_dashboard:OK"]
        
    def test_training_and_probability(self):
        engine = TransitionMatrixEngine(alpha=0.1) # Low smoothing for stronger signals
        
        # Train: A -> B
        trace = [
            {"principal": {"type": "A"}, "action": "act", "outcome": "OK"},
            {"principal": {"type": "B"}, "action": "act", "outcome": "OK"}
        ]
        
        engine.add_trace(trace)
        
        # Check transition A:act:OK -> B:act:OK
        src = "A:act:OK"
        dst = "B:act:OK"
        
        prob = engine.get_probability(src, dst)
        assert prob > 0
        
        # Check unseen transition
        prob_unseen = engine.get_probability(src, "C:act:OK")
        assert prob_unseen > 0 # Non-zero due to smoothing
        assert prob_unseen < prob # But lower than observed
        
    def test_sliding_window(self):
        engine = TransitionMatrixEngine()
        
        trace1 = [
            {"principal": {"type": "A"}, "action": "1", "outcome": "OK"},
            {"principal": {"type": "B"}, "action": "1", "outcome": "OK"}
        ]
        
        engine.add_trace(trace1)
        assert engine.total_traces == 1
        src = "A:1:OK"
        dst = "B:1:OK"
        count_before = engine.edge_counts[(src, dst)]
        
        # Expire
        engine.expire_oldest()
        assert engine.total_traces == 0
        
        # Counts should decrement
        assert engine.edge_counts[(src, dst)] == count_before - 1
        
    def test_scoring(self):
        engine = TransitionMatrixEngine()
        
        # Train basic pattern A -> B
        trace = [
            {"principal": {"type": "A"}, "action": "1", "outcome": "OK"},
            {"principal": {"type": "B"}, "action": "1", "outcome": "OK"}
        ]
        for _ in range(10):
            engine.add_trace(trace)
            
        # Score normal trace
        score_normal = engine.score_trace(trace)
        
        # Score anomaly trace A -> C
        anomaly = [
            {"principal": {"type": "A"}, "action": "1", "outcome": "OK"},
            {"principal": {"type": "C"}, "action": "1", "outcome": "OK"}
        ]
        score_anomaly = engine.score_trace(anomaly)
        
        assert score_anomaly > score_normal
