import requests
import time
import uuid
import sys

GATEWAY_URL = "http://localhost:8080"
AIOPS_URL = "http://localhost:8200"

def get_integrity_metrics():
    try:
        return requests.get(f"{AIOPS_URL}/metrics/integrity", timeout=2).json()
    except Exception as e:
        print(f"Failed to get metrics: {e}")
        return {}

def generate_traces(count=150):
    print(f"Generating {count} traces via Gateway...")
    for i in range(count):
        correlation_id = str(uuid.uuid4())
        
        # Event 1: Login
        payload1 = {
            "event_type": "user_login",
            "actor": "user_verify",
            "action": "login",
            "resource": "portal",
            "metadata": {"correlation_id": correlation_id}
        }
        res = requests.post(f"{GATEWAY_URL}/api/events", json=payload1)
        if res.status_code != 200:
            print(f"Error sending event: {res.text}")
            
        # Event 2: View Dashboard
        payload2 = {
            "event_type": "view_dashboard",
            "actor": "user_verify",
            "action": "view",
            "resource": "dashboard",
            "metadata": {"correlation_id": correlation_id}
        }
        requests.post(f"{GATEWAY_URL}/api/events", json=payload2)
        
        if i % 10 == 0:
            sys.stdout.write(".")
            sys.stdout.flush()
    print("\nGeneration complete.")

def main():
    print("--- AIOps Model Verification ---")
    
    # 1. Check Initial State
    m = get_integrity_metrics()
    print(f"Initial State: {m}")
    
    # 2. Generate Data
    # 150 traces > 100 threshold for model ready
    generate_traces(count=150)
    
    # 3. Wait for Ingestion and TTL Expiry (Trace Finalization)
    # AIOps polls every 5s.
    # Trace TTL is 60s.
    # So we need to wait at least 65s for traces to finalize and enter the model.
    print("Waiting for Trace TTL (60s) + Ingestion Buffers...")
    
    start_wait = time.time()
    while time.time() - start_wait < 90:
        m = get_integrity_metrics()
        ready = m.get("model_ready", False)
        traces = m.get("training_window_traces", 0)
        active = m.get("stats", {}).get("active_traces", 0)
        
        print(f"Status: Ready={ready}, WindowTraces={traces}, ActiveTraces={active}")
        
        if ready:
            print("✅ Model is READY!")
            return
            
        time.sleep(5)
        
    print("❌ Verification Failed: Model did not become ready within timeout.")
    exit(1)

if __name__ == "__main__":
    main()
