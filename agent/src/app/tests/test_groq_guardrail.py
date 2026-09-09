import os
import sys
import time
import httpx
from dotenv import load_dotenv

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

key = os.getenv("GROQ_API_KEY", "").strip('"')
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

TEST_MODELS = [
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-safeguard-20b",
    "openai/gpt-oss-20b",
]

print("=" * 85)
print(" 🛡️ GROQ GUARDRAIL & DEEPEVAL TARGETED MODEL EVALUATION")
print("=" * 85)

for model in TEST_MODELS:
    print(f"\n--- Testing Model: '{model}' ---")
    
    # Test 1: Guardrail JSON evaluation
    payload_g = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Security Guardrail Judge. Evaluate the user prompt below.\n"
                    "Respond strictly with valid JSON format: {\"is_safe\": true, \"reason\": \"safe query\"} or {\"is_safe\": false, \"reason\": \"unsafe query\"}"
                )
            },
            {"role": "user", "content": "hello, what are the best products for my pregnant cow?"}
        ],
        "temperature": 0.0,
        "max_tokens": 100
    }
    
    t0 = time.time()
    try:
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload_g, timeout=10.0)
        dt = (time.time() - t0) * 1000
        if r.status_code == 200:
            res_content = r.json()["choices"][0]["message"]["content"].strip().replace("\n", " ")
            print(f"   [GUARDRAIL EVAL] Latency: {dt:6.1f} ms | Output: \"{res_content[:100]}\"")
        else:
            print(f"   [GUARDRAIL EVAL] Status: {r.status_code} | Error: {r.text[:80]}")
    except Exception as ex:
        print(f"   [GUARDRAIL EVAL] Exception: {ex}")

    # Test 2: DeepEval Fact Check / Reasoning
    payload_d = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "Analyze if the answer is grounded in context. Respond in 1 line."
            },
            {"role": "user", "content": "Context: MaxaPro-DS increases milk fat in buffaloes.\nAnswer: MaxaPro-DS boosts milk fat.\nIs answer grounded?"}
        ],
        "temperature": 0.0,
        "max_tokens": 100
    }
    
    t0 = time.time()
    try:
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload_d, timeout=10.0)
        dt = (time.time() - t0) * 1000
        if r.status_code == 200:
            res_content = r.json()["choices"][0]["message"]["content"].strip().replace("\n", " ")
            print(f"   [DEEPEVAL REASON] Latency: {dt:6.1f} ms | Output: \"{res_content[:100]}\"")
        else:
            print(f"   [DEEPEVAL REASON] Status: {r.status_code} | Error: {r.text[:80]}")
    except Exception as ex:
        print(f"   [DEEPEVAL REASON] Exception: {ex}")

print("\n" + "=" * 85 + "\n")
