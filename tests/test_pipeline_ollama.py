"""
test_pipeline_ollama.py
=======================
Kiểm tra end-to-end pipeline với Ollama (qwen2.5:7b) theo từng bước.

Chạy từ thư mục rag_service/:
    python tests/test_pipeline_ollama.py

Mỗi bước in ra kết quả rõ ràng để dễ debug.
Testcase: "Nấu phở bò tái, bỏ hành lá"
"""

import json
import logging
import os
import sys
import textwrap
import time

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_REPO_ROOT = os.path.abspath(os.path.join(_SERVICE_ROOT, ".."))
for p in [_SERVICE_ROOT, _REPO_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(os.path.join(_SERVICE_ROOT, ".env"))

logging.basicConfig(
    level=logging.WARNING,          # suppress noisy library logs
    format="%(levelname)s %(name)s - %(message)s",
)

# ---------------------------------------------------------------------------
# Pretty printer helpers
# ---------------------------------------------------------------------------
SEP = "=" * 70

def header(step: int, title: str):
    print(f"\n{SEP}")
    print(f"  STEP {step}: {title}")
    print(SEP)

def ok(label: str, value=None):
    if value is None:
        print(f"  [OK]  {label}")
    else:
        short = str(value)
        if len(short) > 200:
            short = short[:200] + "..."
        print(f"  [OK]  {label}: {short}")

def fail(label: str, detail: str = ""):
    print(f"  [FAIL] {label}" + (f": {detail}" if detail else ""))

def pretty_json(obj, indent=4):
    return json.dumps(obj, ensure_ascii=False, indent=indent)

# ---------------------------------------------------------------------------
# TESTCASE
# ---------------------------------------------------------------------------
USER_INPUT = "Nấu phở bò tái, bỏ hành lá"
TEST_DEBUG_STEPS = os.getenv("TEST_DEBUG_STEPS", "0") == "1"

# ---------------------------------------------------------------------------
# STEP 1 — Ollama reachability
# ---------------------------------------------------------------------------
def step1_check_ollama():
    header(1, "Kiểm tra kết nối Ollama")
    import httpx

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/api")
    model    = os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
    timeout  = int(os.getenv("LLM_TIMEOUT", "120"))

    print(f"  OLLAMA_BASE_URL   = {base_url}")
    print(f"  OLLAMA_TEXT_MODEL = {model}")
    print(f"  LLM_TIMEOUT       = {timeout}s")

    try:
        resp = httpx.get(base_url.replace("/api", ""), timeout=5)
        ok("Ollama server reachable", f"HTTP {resp.status_code}")
    except Exception as exc:
        fail("Ollama server NOT reachable", str(exc))
        raise SystemExit(1)

    # Quick ping with a tiny prompt
    try:
        from app.services.llm_client import LLMClient
        client = LLMClient()
        reply = client.chat(
            messages=[{"role": "user", "content": "Xin chào, hãy trả lời 1 từ."}],
            max_tokens=20,
        )
        ok("LLMClient.chat() works", repr(reply))
        return client
    except Exception as exc:
        fail("LLMClient.chat() failed", str(exc))
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# STEP 2 — Guardrail pre-check
# ---------------------------------------------------------------------------
def step2_guardrail(user_input: str):
    header(2, "Guardrail pre-check (local policy)")
    from app.guardrails.policies import GuardrailPolicyEvaluator

    evaluator = GuardrailPolicyEvaluator()
    # evaluate(prompt_text, response_text) — pass empty string for response at input check stage
    violations = evaluator.evaluate(user_input, "")

    if violations:
        blocked = any(v.action in ("block", "safe-completion") for v in violations)
        if blocked:
            fail("Input BLOCKED by guardrail", str([v.to_dict() for v in violations]))
            raise SystemExit(1)
        ok(f"Input has {len(violations)} warning-level violation(s) but not blocked")
    else:
        ok("Input passed guardrail — no violations")
    return violations


# ---------------------------------------------------------------------------
# STEP 3 — LLM extraction (dish_name, ingredients, excluded_ingredients)
# ---------------------------------------------------------------------------
def step3_extraction(user_input: str, llm_client):
    header(3, "LLM Extraction — tên món & nguyên liệu")
    from app.services.llm_model_service import LLMModelService

    svc = LLMModelService(llm_client=llm_client)
    result = svc.extract_dish_name(user_input)

    print("\n  Raw extraction result:")
    print(textwrap.indent(pretty_json(result), "    "))

    dish_name = result.get("dish_name")
    if not dish_name:
        fail("dish_name missing from extraction")
        raise SystemExit(1)

    ok("dish_name", dish_name)
    ok("ingredients",          result.get("ingredients"))
    ok("excluded_ingredients", result.get("excluded_ingredients"))
    return result


# ---------------------------------------------------------------------------
# STEP 4 — Pinecone retrieval
# ---------------------------------------------------------------------------
def step4_retrieval(dish_name: str):  # noqa: returns (results, retriever)
    header(4, "Pinecone retrieval — tìm tài liệu cho món")
    from app.services.pinecone_kb_service import _build_retriever

    print(f"  Querying Pinecone for: '{dish_name}'")
    try:
        retriever = _build_retriever()
        ok("Retriever initialised")
    except Exception as exc:
        fail("Failed to build retriever", str(exc))
        raise SystemExit(1)

    query = f"Tìm đúng món: {dish_name}"
    results = retriever.search_filtered(query_text=query, top_k=5, type_filter="dish")

    if not results:
        fail("No results from Pinecone")
        raise SystemExit(1)

    ok(f"Retrieved {len(results)} document(s)")
    for i, r in enumerate(results, 1):
        print(f"    [{i}] score={r['score']:.4f}  name_vi={r.get('name_vi')}  text={r.get('text','')[:80]}...")
    return results, retriever


# ---------------------------------------------------------------------------
# STEP 5 — Recipe generation (LLM)
# ---------------------------------------------------------------------------
def step5_recipe(dish_name: str, llm_client, retriever=None):
    header(5, "Recipe generation — LLM trích xuất công thức từ tài liệu")
    from app.services.pinecone_kb_service import PineconeKBService

    # Pass the already-initialised retriever to avoid loading the 2 GB model twice
    kb = PineconeKBService(llm_client=llm_client, retriever=retriever)
    recipe = kb.get_dish_recipe(dish_name)

    print("\n  Recipe result:")
    print(textwrap.indent(pretty_json(recipe), "    "))

    ingredients = recipe.get("ingredients", [])
    if not ingredients:
        fail("Recipe returned no ingredients")
        raise SystemExit(1)

    ok(f"Recipe has {len(ingredients)} ingredient(s)")
    return recipe


# ---------------------------------------------------------------------------
# STEP 6 — Full pipeline (process)
# ---------------------------------------------------------------------------
def step6_full_pipeline(user_input: str, llm_client, retriever):
    header(6, "Full ShoppingCartPipeline.process()")
    from app.pipeline import ShoppingCartPipeline

    print(f"  Input: \"{user_input}\"")
    print("  Initialising pipeline (this loads ontology + embedding model)...")

    pipeline = ShoppingCartPipeline()
    # Reuse already initialised clients to avoid loading the large embedding model twice.
    pipeline.kb_service._llm = llm_client
    pipeline.kb_service._retriever = retriever
    pipeline.kb_service._init_done = True

    response = pipeline.process(user_input)

    print("\n  Final response:")
    print(textwrap.indent(pretty_json(response), "    "))

    status = response.get("status") or response.get("code", "")
    items  = response.get("cart_items") or response.get("ingredients") or []

    if str(status).startswith("error"):
        fail("Pipeline returned error status", status)
    else:
        ok("Pipeline status", status)
        ok(f"Cart items count", len(items))

    return response


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    testcase_start = time.perf_counter()

    print(f"\n{'#'*70}")
    print(f"  PIPELINE OLLAMA TEST — testcase: \"{USER_INPUT}\"")
    print(f"{'#'*70}")

    try:
        llm_client = step1_check_ollama()

        if TEST_DEBUG_STEPS:
            # Full debug flow: executes extraction/retrieval/recipe first, then full pipeline.
            # This mode is intentionally slower and should not be used for production latency benchmarking.
            step2_guardrail(USER_INPUT)
            extracted = step3_extraction(USER_INPUT, llm_client)
            dish_name = extracted["dish_name"]
            _, retriever = step4_retrieval(dish_name)
            step5_recipe(dish_name, llm_client, retriever)
            step6_full_pipeline(USER_INPUT, llm_client, retriever)
        else:
            # Benchmark mode: run a single end-to-end pipeline call for realistic latency.
            header(2, "Benchmark mode — single pipeline call")
            from app.pipeline import ShoppingCartPipeline
            pipeline = ShoppingCartPipeline()
            response = pipeline.process(USER_INPUT)
            print("\n  Final response:")
            print(textwrap.indent(pretty_json(response), "    "))

        print(f"\n{'#'*70}")
        print("  ALL STEPS COMPLETED")
        print(f"{'#'*70}\n")
    finally:
        testcase_elapsed = time.perf_counter() - testcase_start
        print(f"  Testcase query time: {testcase_elapsed:.2f}s")


if __name__ == "__main__":
    main()
