import httpx
try:
    with httpx.Client(timeout=0.1) as client:
        resp = client.get("http://localhost:11434")
        print(f"Status: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
