from typing import Dict, Tuple, Deque, List
from collections import defaultdict, deque
import logging
import math

logger = logging.getLogger("aiops-markov")

State = str # "Actor:Action:Outcome"

class TransitionMatrixEngine:
    """
    Sparse, incremental Markov Model.
    Maintains transition counts for a sliding window of traces.
    """
    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        
        # Core Model: Sparse Counts
        self.edge_counts: Dict[Tuple[State, State], int] = defaultdict(int)
        self.out_counts: Dict[State, int] = defaultdict(int)
        self.states: set[State] = set()
        
        # Sliding Window Management
        # We store minimal trace info to support expiration (decrementing counts)
        self.window_traces: Deque[List[State]] = deque()
        self.total_traces = 0

    def _extract_sequence(self, trace_events: List[dict]) -> List[State]:
        """Convert raw events to state sequence."""
        seq = []
        for event in trace_events:
            try:
                # State Definition: ActorType:Action:Outcome
                actor = "unknown"
                principal = event.get("principal") or event.get("agent_id")
                if isinstance(principal, dict):
                    actor = principal.get("type", "unknown")
                elif isinstance(principal, str):
                    actor = "service" if principal in ["gateway", "audit-service"] else "user"
                
                # Action Normalization
                action = event.get("action")
                if not action or isinstance(action, dict):
                    action = event.get("method")
                if not action or isinstance(action, dict):
                    action = event.get("http", {}).get("path", "unknown")
                
                action_str = str(action)
                if "/api/events" in action_str: action_str = "emit_audit"
                if "/mcp/tools" in action_str: action_str = "tool_use"
                # Strip IDs? Assumed handled by 'method' usually being clean 
                # but raw paths might leak IDs.
                
                outcome = event.get("outcome", "OK")
                
                state = f"{actor}:{action_str}:{outcome}"
                seq.append(state)
            except Exception:
                continue
        return seq

    def add_trace(self, trace_events: List[dict]):
        """Ingest a finalized trace into the current window."""
        seq = self._extract_sequence(trace_events)
        if not seq:
            return

        self.window_traces.append(seq)
        self.total_traces += 1
        
        # Update Counts
        for i in range(len(seq) - 1):
            src, dst = seq[i], seq[i+1]
            self.edge_counts[(src, dst)] += 1
            self.out_counts[src] += 1
            self.states.add(src)
            self.states.add(dst)

    def expire_oldest(self):
        """Remove the oldest trace from the window (sliding logic)."""
        if not self.window_traces:
            return

        seq = self.window_traces.popleft()
        self.total_traces -= 1
        
        # Decrement Counts
        for i in range(len(seq) - 1):
            src, dst = seq[i], seq[i+1]
            if self.edge_counts[(src, dst)] > 0:
                self.edge_counts[(src, dst)] -= 1
            if self.out_counts[src] > 0:
                self.out_counts[src] -= 1
            
            # We don't remove states from self.states set to avoid thrashing,
            # sparse map handles zero counts fine.

    def get_probability(self, src: State, dst: State) -> float:
        """Calculate smoothed transition probability."""
        count = self.edge_counts.get((src, dst), 0)
        total_out = self.out_counts.get(src, 0)
        num_states = len(self.states)
        
        # Laplace Smoothing
        # P = (count + alpha) / (total_out + alpha * num_states)
        if num_states == 0:
            return 0.0
            
        prob = (count + self.alpha) / (total_out + self.alpha * num_states)
        return prob

    def score_trace(self, trace_events: List[dict]) -> float:
        """
        Calculate Sequence Likelihood Score.
        Score = Sum(-log(P))
        Higher score = More Anomalous.
        """
        seq = self._extract_sequence(trace_events)
        if len(seq) < 2:
            return 0.0
            
        score = 0.0
        for i in range(len(seq) - 1):
            src, dst = seq[i], seq[i+1]
            prob = self.get_probability(src, dst)
            # Log probability
            if prob > 0:
                score += -math.log(prob)
            else:
                # Should not happen with smoothing, but safeguard
                score += 100.0 # Penalty
                
        return score / len(seq) # Normalize by length? Or keep absolute? User agreed to "Sequence Likelihood".
        # Plan said: score = sum of -log(p). Alert if > percentile.
