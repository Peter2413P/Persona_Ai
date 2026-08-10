import requests

BASE_URL = "http://localhost:8000"
persona_id = "7190a364-9a3f-4c7f-acf1-2932939c5ca2"

print("Re-ingesting Wikipedia URL to populate new metadata tags...", flush=True)

url = "https://en.wikipedia.org/wiki/Vijay_filmography"

payload = {
    "persona_id": persona_id,
    "url": url
}

r = requests.post(f"{BASE_URL}/knowledge/url", json=payload)
print(r.json(), flush=True)
