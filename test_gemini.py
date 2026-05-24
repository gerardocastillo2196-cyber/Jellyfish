import httpx
import os

key = os.getenv("GEMINI_API_KEY")
url = "https://generativelanguage.googleapis.com/v1beta/models?key=" + str(key)
try:
    resp = httpx.get(url)
    print(resp.status_code)
    data = resp.json()
    for m in data.get("models", []):
        print(m["name"])
except Exception as e:
    print(e)
