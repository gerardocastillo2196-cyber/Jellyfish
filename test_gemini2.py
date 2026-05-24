import httpx
import os

key = os.getenv("GEMINI_API_KEY")
url = "https://generativelanguage.googleapis.com/v1beta/models?key=" + str(key)
try:
    resp = httpx.get(url)
    print(resp.status_code)
    print(resp.json())
except Exception as e:
    print(e)
