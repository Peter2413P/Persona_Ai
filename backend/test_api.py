import requests
import json
import time

BASE_URL = "http://localhost:8000"

def get_latest_persona():
    resp = requests.get(f"{BASE_URL}/personas/")
    personas = resp.json()
    if not personas:
        print("No personas found!")
        return None
    return personas[-1]["id"]

def run_test(persona_id, query, history=[]):
    print(f"\n{'='*50}\nTESTING: {query}")
    payload = {
        "persona_id": persona_id,
        "message": query,
        "history": history
    }
    try:
        with requests.post(f"{BASE_URL}/chat/stream", json=payload, stream=True) as resp:
            print(f"Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"Response: {resp.text}")
                
            full_response = ""
            for line in resp.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data: '):
                        data_str = decoded[6:]
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "token":
                                content = data.get("content", "")
                                full_response += content
                                print(content, end="", flush=True)
                            elif data.get("type") == "error":
                                print(f"\n[ERROR] {data.get('message')}")
                        except json.JSONDecodeError:
                            pass
            print("\n")
            return full_response
    except Exception as e:
        print(f"\n[EXCEPTION] {e}\n")
        return ""

if __name__ == "__main__":
    pid = get_latest_persona()
    if pid:
        tests = [
            # TEST 1
            "What was Vijay's first film?",
            # TEST 2
            "What was Vijay's first film as a lead actor?",
            # TEST 3
            "What was Vijay's 50th film?",
            # TEST 4
            "Which Vijay films had multiple roles?",
            # TEST 5
            "Which films featured Vijay in a guest appearance?",
            # TEST 6
            "What roles did Vijay play in Mersal?",
            # TEST 7
            "Which movies did Vijay act in during 1995?",
            # TEST 8
            "List Vijay movies from 2010 to 2020",
        ]
        
        for q in tests:
            run_test(pid, q)
            time.sleep(1)
            
        # TEST 9: Conversation Follow-up
        print("\n" + "="*50 + "\nRUNNING FOLLOW UP CONVERSATION TEST")
        q1 = "Who played the lead role in Mersal?"
        ans1 = run_test(pid, q1)
        history = [
            {"role": "user", "content": q1},
            {"role": "assistant", "content": ans1}
        ]
        time.sleep(1)
        q2 = "What roles did he play?"
        run_test(pid, q2, history)
        
        # TEST 10: Not Found
        time.sleep(1)
        run_test(pid, "What role did Vijay play in Avatar 2?")
