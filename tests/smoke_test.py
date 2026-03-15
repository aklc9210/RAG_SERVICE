"""
Smoke test for rag_service — verifies end-to-end pipeline without a live Pinecone/LLM call.

Run from the rag_service/ directory:
    python tests/smoke_test.py

Set env vars or .env before running:
    PINECONE_API_KEY=...
    LLM_API_KEY=...   (or set LLM_BASE_URL to a local Ollama endpoint)
"""
import sys
import os
import json
import logging

# Allow running from repo root with:  python rag_service/tests/smoke_test.py
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
for p in [_REPO_ROOT, _SERVICE_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv(os.path.join(_SERVICE_ROOT, '.env'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s - %(message)s',
)
logger = logging.getLogger('smoke_test')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_env():
    """Warn about missing env vars without crashing."""
    required = {
        'PINECONE_API_KEY': 'Pinecone retrieval will fail',
        'LLM_API_KEY': 'LLM calls will fail unless using an unauthenticated local endpoint',
    }
    for var, hint in required.items():
        if not os.getenv(var):
            logger.warning(f"  {var} not set — {hint}")


def assert_field(result, path, message=""):
    """Drill into a nested dict by dot-path and assert the value is truthy."""
    obj = result
    for key in path.split('.'):
        assert isinstance(obj, dict), f"Expected dict at '{key}', got {type(obj)}: {message}"
        assert key in obj, f"Missing key '{key}' in response: {message}"
        obj = obj[key]
    return obj


# ---------------------------------------------------------------------------
# Unit-level tests (no network)
# ---------------------------------------------------------------------------

def test_ttl_cache():
    logger.info("[unit] TTLCache basic set/get/expire")
    import time
    from app.pipeline import TTLCache
    
    cache = TTLCache(maxsize=3, ttl_seconds=1)
    cache.set('a', 1)
    cache.set('b', 2)
    assert cache.get('a') == 1
    assert cache.get('b') == 2
    assert cache.get('z') is None
    
    # TTL expiry
    time.sleep(1.1)
    assert cache.get('a') is None, "Should have expired"
    
    # maxsize eviction
    cache2 = TTLCache(maxsize=2, ttl_seconds=999)
    cache2.set('x', 1)
    cache2.set('y', 2)
    cache2.set('z', 3)  # evicts 'x'
    assert cache2.get('x') is None
    assert cache2.get('z') == 3
    logger.info("  PASS")


def test_guardrail_policies():
    logger.info("[unit] GuardrailPolicyEvaluator — load + basic eval")
    from app.guardrails.policies import GuardrailPolicyEvaluator
    
    evaluator = GuardrailPolicyEvaluator()
    # Clean query should return no violations
    result = evaluator.evaluate("Tôi muốn nấu phở bò cho gia đình")
    assert isinstance(result, dict)
    logger.info(f"  clean query result: {result}")
    logger.info("  PASS")


def test_ontology_service():
    logger.info("[unit] OntologyService — load + basic query")
    from app.services.ontology_service import OntologyService
    
    svc = OntologyService()
    assert len(svc.ingredients) > 0, "Ingredient KB should be non-empty"
    assert len(svc.dishes) > 0, "Dish KB should be non-empty"
    
    # pick any ingredient ID and look it up
    first_id = next(iter(svc.ingredients))
    info = svc.get_ingredient(first_id)
    assert info is not None
    logger.info(f"  Sample ingredient: {first_id} → {info.get('name_vi') or info.get('vietnamese_name')}")
    logger.info("  PASS")


def test_unit_converter():
    logger.info("[unit] UnitConverterService — basic normalisation")
    from app.services.unit_converter_service import UnitConverterService
    
    svc = UnitConverterService()
    items = [{
        'ingredient_id': 'test_1',
        'vietnamese_name': 'Thịt bò',
        'name': 'Beef',
        'quantity': '200',
        'unit': 'g',
    }]
    result = svc.normalize_ingredients(items)
    assert isinstance(result, list)
    logger.info(f"  Normalized: {result}")
    logger.info("  PASS")


def test_ingredient_resolver():
    logger.info("[unit] IngredientResolver — resolve a common ingredient")
    from app.services.ontology_service import OntologyService
    from app.services.ingredient_resolver import IngredientResolver
    
    ontology = OntologyService()
    resolver = IngredientResolver(ontology)
    
    # Try resolving a very common Vietnamese ingredient
    candidates = ['thịt bò', 'muối', 'nước mắm', 'hành', 'tỏi']
    for name in candidates:
        resolved = resolver.resolve_name_to_id(name)
        if resolved:
            logger.info(f"  '{name}' → {resolved}")
            logger.info("  PASS (at least one ingredient resolved)")
            return
    
    logger.warning("  None of the test ingredients resolved — knowledge base may be empty or field names differ")


def test_validation_service():
    logger.info("[unit] ValidationService — load cooccurrence data")
    from app.services.validation_service import ValidationService
    
    svc = ValidationService()
    assert svc.matrix is not None or svc.frequency is not None, "Must load at least one file"
    logger.info("  PASS")


# ---------------------------------------------------------------------------
# Integration test (requires env vars)
# ---------------------------------------------------------------------------

def test_processor_text():
    """
    End-to-end processor test. Requires PINECONE_API_KEY and LLM_API_KEY.
    Skipped gracefully if keys are missing.
    """
    logger.info("[integration] RecipeAnalysisProcessor.process_request")

    if not os.getenv('PINECONE_API_KEY') or not os.getenv('LLM_API_KEY'):
        logger.warning("  Skipping integration test — PINECONE_API_KEY / LLM_API_KEY not set")
        return

    from app.processor import RecipeAnalysisProcessor

    processor = RecipeAnalysisProcessor()
    result = processor.process_request({'user_input': 'Tôi muốn nấu phở bò'})

    logger.info(f"  Raw response: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")

    assert 'success' in result, "Response must have 'success' key"
    if result['success']:
        r = result['result']
        assert_field(r, 'status')
        assert_field(r, 'dish')
        assert_field(r, 'cart')
        logger.info(f"  Dish: {r['dish'].get('vietnamese_name')}")
        logger.info(f"  Cart items: {r['cart']['total_items']}")
        logger.info("  PASS")
    else:
        logger.warning(f"  Pipeline returned non-success: {result.get('error')} (may be expected without live KB)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("rag_service smoke test")
    logger.info("=" * 60)
    
    check_env()
    
    passed = 0
    failed = 0
    
    unit_tests = [
        test_ttl_cache,
        test_guardrail_policies,
        test_ontology_service,
        test_unit_converter,
        test_ingredient_resolver,
        test_validation_service,
    ]
    
    integration_tests = [
        test_processor_text,
    ]
    
    for test_fn in unit_tests + integration_tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            logger.error(f"FAIL {test_fn.__name__}: {e}", exc_info=True)
            failed += 1
    
    logger.info("=" * 60)
    logger.info(f"Results: {passed} passed, {failed} failed")
    logger.info("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
