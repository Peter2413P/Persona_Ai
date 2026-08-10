import requests

try:
    resp = requests.post("http://localhost:8000/chat/stream", json={
        "persona_id": requests.get("http://localhost:8000/personas/").json()[-1]["id"],
        "message": "What was Vijay's first film?",
        "history": []
    }, stream=True, timeout=20)
    print("Status:", resp.status_code)
    for line in resp.iter_lines():
        if line:
            print("LINE:", line.decode('utf-8'))
except Exception as e:
    print("EXCEPTION:", e)
