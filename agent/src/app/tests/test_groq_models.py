import os
import sys
import time
import asyncio

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip('"')

# Models to test from Groq Dashboard
TEST_MODELS = [
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-120b",
    "groq/compound-mini",
    "groq/compound",
    "meta-llama/llama-prompt-guard-2-86m",
]

TEST_QUERIES = [
    {
        "name": "Guardrail Safety Check",
        "prompt": "Evaluate if this user query is safe or unsafe for a livestock feed assistant: 'hello, what are the best products for my pregnant cow?' Reply ONLY with 'SAFE' or 'UNSAFE'."
    },
    {
        "name": "Fact Extraction & Reasoning",
        "prompt": "Summarize in 1 concise sentence the key benefit of feeding high-protein supplements to dairy buffaloes."
    }
]


async def benchmark_model(model_name: str, query_info: dict):
    llm = ChatOpenAI(
        model=model_name,
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        temperature=0.0
    )

    start_time = time.time()
    first_token_time = None
    full_text = ""

    try:
        async for chunk in llm.astream([HumanMessage(content=query_info["prompt"])]):
            if first_token_time is None:
                first_token_time = time.time()
            if hasattr(chunk, "content") and isinstance(chunk.content, str):
                full_text += chunk.content

        end_time = time.time()
        ttft_ms = ((first_token_time - start_time) * 1000) if first_token_time else 0.0
        total_latency = end_time - start_time

        return {
            "model": model_name,
            "test": query_info["name"],
            "status": "SUCCESS",
            "ttft_ms": round(ttft_ms, 1),
            "latency_s": round(total_latency, 2),
            "output": full_text.strip().replace("\n", " ")[:120]
        }
    except Exception as e:
        return {
            "model": model_name,
            "test": query_info["name"],
            "status": "FAILED",
            "error": str(e)[:120]
        }


async def run_all_benchmarks():
    print("\n" + "=" * 75)
    print(" 🚀 GROQ ACTIVE MODELS BENCHMARK SCORECARD")
    print(f" API KEY: {GROQ_API_KEY[:10]}...{GROQ_API_KEY[-6:]}")
    print("=" * 75 + "\n")

    results = []
    for model in TEST_MODELS:
        print(f"Testing model: '{model}'...")
        for query in TEST_QUERIES:
            res = await benchmark_model(model, query)
            results.append(res)
            if res["status"] == "SUCCESS":
                print(f"   [SUCCESS] {res['test']} | TTFT: {res['ttft_ms']}ms | Total: {res['latency_s']}s")
                print(f"             Output: \"{res['output']}\"")
            else:
                print(f"   [FAILED]  {res['test']} | Error: {res['error']}")
        print("-" * 75)

    print("\n" + "=" * 75)
    print(" 📊 FINAL GROQ MODEL PERFORMANCE COMPARISON SUMMARY")
    print("=" * 75)
    print(f"{'MODEL':<35} | {'TEST':<22} | {'STATUS':<8} | {'TTFT (ms)':<10} | {'TOTAL (s)'}")
    print("-" * 85)
    for r in results:
        status_str = r["status"]
        ttft_str = str(r.get("ttft_ms", "N/A"))
        lat_str = str(r.get("latency_s", "N/A"))
        print(f"{r['model']:<35} | {r['test']:<22} | {status_str:<8} | {ttft_str:<10} | {lat_str}")
    print("=" * 85 + "\n")

if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())
