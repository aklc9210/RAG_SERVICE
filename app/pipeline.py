# app/pipeline.py
# Adapted from AI_service/app/main_optimized.py
# Bedrock model calls replaced with LLMModelService
# Bedrock KB retrieval replaced with PineconeKBService
# All business logic (ontology, conflict, suggestions, unit conversion) kept intact

"""
ShoppingCartPipeline — replacement for OptimizedShoppingCartPipeline.

Differences from the original:
  - self.extractor = LLMModelService()           (was BedrockModelService)
  - self.kb_service = PineconeKBService()        (was BedrockKBService)
  - No S3ImageService (image path not in scope for new stack)
  - _apply_contextual_grounding removed (was Bedrock-only)
  - Everything else is preserved as-is
"""

from dotenv import load_dotenv
from typing import Dict, List, Optional, Tuple
import logging
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from app.services.llm_model_service import LLMModelService
from app.services.pinecone_kb_service import PineconeKBService
from app.services.unit_converter_service import UnitConverterService
from app.services.validation_service import ValidationService
from app.services.ontology_service import OntologyService
from app.services.conflict_service import ConflictDetectionService
from app.services.ingredient_resolver import IngredientResolver
from app.services.suggestion_service import SuggestionService

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TTL Cache (unchanged from AI_service)
# ---------------------------------------------------------------------------

class TTLCache:
    """Simple TTL (Time-To-Live) cache implementation."""

    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 3600):
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds

    def get(self, key: str) -> Optional[object]:
        if key not in self.cache:
            return None
        if time.time() - self.timestamps[key] > self.ttl_seconds:
            del self.cache[key]
            del self.timestamps[key]
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: object) -> None:
        if len(self.cache) >= self.maxsize and key not in self.cache:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]
        self.cache[key] = value
        self.cache.move_to_end(key)
        self.timestamps[key] = time.time()

    def clear(self) -> None:
        self.cache.clear()
        self.timestamps.clear()

    def size(self) -> int:
        return len(self.cache)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class ShoppingCartPipeline:
    """
    Full replacement for OptimizedShoppingCartPipeline.
    Uses Pinecone retrieval + new LLM instead of Bedrock KB + Bedrock model.
    """

    def __init__(self, max_workers: int = 3, recipe_cache_ttl: int = 3600):
        self.extractor = LLMModelService()
        self.kb_service = PineconeKBService()
        self.converter = UnitConverterService()
        self.validator = ValidationService()
        self.ontology = OntologyService()
        self.conflicts = ConflictDetectionService()

        self.ingredient_resolver = IngredientResolver(self.ontology)
        self.suggestion_service = SuggestionService(self.ontology, self.converter, self.validator)

        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        self._recipe_cache = TTLCache(maxsize=1000, ttl_seconds=recipe_cache_ttl)
        self._ingredient_id_cache: Dict[str, Optional[str]] = {}
        self._ingredient_info_cache: Dict[str, Dict] = {}

        self._build_ingredient_index()
        logger.info(f"ShoppingCartPipeline initialized (workers={max_workers}, TTL={recipe_cache_ttl}s)")

    # ------------------------------------------------------------------
    # Public entry points (same interface as OptimizedShoppingCartPipeline)
    # ------------------------------------------------------------------

    def process(self, user_input: str) -> dict:
        """Process text input."""
        extracted = self.extractor.extract_dish_name(user_input)
        return self._build_response(extracted, user_query=user_input)

    # ------------------------------------------------------------------
    # Pre-built index for O(1) exact lookups
    # ------------------------------------------------------------------

    def _build_ingredient_index(self):
        self._ingredient_name_index = {}
        for ing_id, ing_info in self.ontology.ingredients.items():
            name_vi = (ing_info.get('name_vi') or ing_info.get('vietnamese_name') or '').lower().strip()
            if name_vi:
                self._ingredient_name_index[name_vi] = ing_id
            name_en = (ing_info.get('name_en') or ing_info.get('name') or '').lower().strip()
            if name_en:
                self._ingredient_name_index[name_en] = ing_id
        logger.info(f"Built ingredient index with {len(self._ingredient_name_index)} entries")

    # ------------------------------------------------------------------
    # Core response builder (logic preserved from OptimizedShoppingCartPipeline)
    # ------------------------------------------------------------------

    def _build_response(self, extracted: dict, user_query: str = "") -> dict:
        if not extracted:
            return self._error_response('extraction_failed')

        guardrail_info = extracted.get('guardrail')
        warnings = self._normalize_warnings(extracted.get('warnings'))

        is_guardrail_blocked = (
            guardrail_info and
            guardrail_info.get('action') in ['block', 'blocked'] and
            guardrail_info.get('triggered') is True
        )

        guardrail_messages = extracted.get('guardrail_messages')
        if guardrail_messages:
            has_guardrail_warnings = any(
                w.get('details', {}).get('policy_id') for w in warnings
            )
            if not has_guardrail_warnings:
                warnings.extend(self._guardrail_warnings(guardrail_info, guardrail_messages))
        elif guardrail_info and guardrail_info.get('triggered'):
            warnings.extend(self._guardrail_warnings(guardrail_info, None))

        dish_name = extracted.get('dish_name')
        extra_ingredients = extracted.get('ingredients', [])
        excluded_ingredients = extracted.get('excluded_ingredients', [])

        if not dish_name:
            if is_guardrail_blocked:
                return self._error_response('guardrail_violation', guardrail_info, warnings)
            elif extra_ingredients:
                warnings.append({
                    'message': 'Không tìm thấy tên món, chỉ xử lý danh sách nguyên liệu',
                    'severity': 'info',
                    'source': 'system',
                    'details': {}
                })
                recipe = {'ingredients': []}
                recipe_ing = []
            else:
                return self._error_response('dish_not_found', guardrail_info, warnings)
        else:
            recipe = self._get_recipe(dish_name)
            if not recipe.get('ingredients'):
                return self._error_response('recipe_not_found', guardrail_info, warnings, dish_name)
            recipe_ing = self._normalize_recipe_items_batch(recipe.get('ingredients', []))

        extra_norm = self._normalize_extra_batch(extra_ingredients)

        excluded_ids = self._resolve_excluded_ingredients_batch(excluded_ingredients)
        if excluded_ids:
            recipe_ing = [
                item for item in recipe_ing
                if item.get('ingredient_id') not in excluded_ids
            ]

        all_ingredients = recipe_ing + [it for it in extra_norm if it.get('ingredient_id')]

        if not all_ingredients:
            return self._error_response('no_valid_ingredients', guardrail_info, warnings, dish_name)

        cart_items = self.converter.normalize_ingredients(all_ingredients)
        self._add_categories_batch(cart_items)

        ingredient_ids = [item['ingredient_id'] for item in cart_items]

        futures = {
            'suggestions': self.executor.submit(
                self._get_suggestions, ingredient_ids, dish_name or ''
            ),
            'similar_dishes': self.executor.submit(
                self.ontology.search_similar_dishes,
                [item['ingredient_id'] for item in all_ingredients],
                3
            ),
            'conflicts': self.executor.submit(
                self._check_conflicts_parallel,
                dish_name or '',
                cart_items,
                extra_ingredients
            )
        }

        suggestions = futures['suggestions'].result()
        similar = futures['similar_dishes'].result()
        conflict_warnings, insights = futures['conflicts'].result()

        warnings.extend(conflict_warnings)

        return {
            'status': 'success',
            'error': None,
            'error_type': None,
            's3_url': '',
            'dish': {
                'vietnamese_name': recipe.get('vietnamese_name') or dish_name or '',
                'name': recipe.get('name') or '',
                'prep_time': recipe.get('prep_time') if dish_name else None,
                'servings': recipe.get('servings') if dish_name else None,
            },
            'cart': {
                'total_items': len(cart_items),
                'items': cart_items,
            },
            'suggestions': suggestions,
            'similar_dishes': similar[:3],
            'excluded_ingredients': self._normalize_excluded_ingredients_batch(excluded_ingredients),
            'warnings': self._unique_warnings(warnings),
            'insights': insights,
            'guardrail': guardrail_info,
        }

    # ------------------------------------------------------------------
    # Cached lookups
    # ------------------------------------------------------------------

    def _resolve_name_to_ingredient_id_cached(self, name: str) -> Optional[str]:
        if name in self._ingredient_id_cache:
            return self._ingredient_id_cache[name]

        name_lower = name.lower().strip()
        if name_lower in self._ingredient_name_index:
            result = self._ingredient_name_index[name_lower]
            self._ingredient_id_cache[name] = result
            return result

        result = self.ingredient_resolver.resolve_name_to_id(name)
        self._ingredient_id_cache[name] = result
        return result

    def _get_ingredient_info_cached(self, ingredient_id: str) -> Dict:
        if ingredient_id in self._ingredient_info_cache:
            return self._ingredient_info_cache[ingredient_id]
        result = self.ontology.get_ingredient(ingredient_id) or {}
        self._ingredient_info_cache[ingredient_id] = result
        return result

    # ------------------------------------------------------------------
    # Batch normalisation helpers (preserved from OptimizedShoppingCartPipeline)
    # ------------------------------------------------------------------

    def _normalize_recipe_items_batch(self, items: list) -> list:
        if not items:
            return []
        normalized = []
        for it in items:
            vietnamese_name = str(it.get('vietnamese_name') or it.get('name_vi') or '').strip()
            english_name = str(it.get('name') or it.get('name_en') or '').strip()

            if not vietnamese_name and it.get('name'):
                vietnamese_name = str(it.get('name')).strip()
                english_name = ''

            if not vietnamese_name:
                continue

            ing_id = self._resolve_name_to_ingredient_id_cached(vietnamese_name)
            if not ing_id:
                continue

            ing_info = self._get_ingredient_info_cached(ing_id)

            qty = it.get('quantity', '')
            if isinstance(qty, (int, float)):
                qty = str(qty)
            elif not isinstance(qty, str):
                qty = ''

            normalized.append({
                'ingredient_id': ing_id,
                'vietnamese_name': vietnamese_name,
                'name': english_name or ing_info.get('name_en', '') or ing_info.get('name', ''),
                'quantity': qty,
                'unit': str(it.get('unit', '')),
            })
        return normalized

    def _normalize_extra_batch(self, extra_ingredients: list) -> list:
        if not extra_ingredients:
            return []
        normalized = []
        for item in extra_ingredients:
            vietnamese_name = (
                item.get('vietnamese_name', '').strip()
                or item.get('name_vi', '').strip()
                or item.get('name', '').strip()
            )
            english_name = item.get('name', '').strip() or item.get('name_en', '').strip()

            if not vietnamese_name:
                continue

            matched_id = self._resolve_name_to_ingredient_id_cached(vietnamese_name)
            if matched_id:
                ing_data = self._get_ingredient_info_cached(matched_id)
                qty = item.get('quantity', '')
                if isinstance(qty, (int, float)):
                    qty = str(qty)
                elif not isinstance(qty, str):
                    qty = ''
                normalized.append({
                    'ingredient_id': matched_id,
                    'vietnamese_name': ing_data.get('vietnamese_name') or ing_data.get('name_vi', vietnamese_name),
                    'name': english_name or ing_data.get('name_en', '') or ing_data.get('name', ''),
                    'quantity': qty,
                    'unit': str(item.get('unit', '')),
                })
        return normalized

    def _resolve_excluded_ingredients_batch(self, excluded: list) -> set:
        if not excluded:
            return set()
        excluded_ids = set()
        for exc in excluded:
            name = exc.get('name', '').strip()
            if name:
                matched_id = self._resolve_name_to_ingredient_id_cached(name)
                if matched_id:
                    excluded_ids.add(matched_id)
        return excluded_ids

    def _normalize_excluded_ingredients_batch(self, excluded: list) -> list:
        if not excluded:
            return []
        normalized = []
        for exc in excluded:
            name = exc.get('name', '').strip()
            reason = exc.get('reason', '').strip()
            if not name:
                continue
            matched_id = self._resolve_name_to_ingredient_id_cached(name)
            if matched_id:
                ing_info = self._get_ingredient_info_cached(matched_id)
                normalized.append({
                    'ingredient_id': matched_id,
                    'vietnamese_name': ing_info.get('vietnamese_name') or ing_info.get('name_vi', name),
                    'name': ing_info.get('name') or ing_info.get('name_en', ''),
                    'category': ing_info.get('category', ''),
                    'reason': reason,
                })
            else:
                normalized.append({
                    'ingredient_id': '',
                    'vietnamese_name': name,
                    'name': '',
                    'category': '',
                    'reason': reason,
                })
        return normalized

    def _add_categories_batch(self, cart_items: list) -> None:
        for item in cart_items:
            ing_info = self._get_ingredient_info_cached(item['ingredient_id'])
            item['category'] = ing_info.get('category', 'other')
            if 'vietnamese_name' not in item:
                item['vietnamese_name'] = ing_info.get('vietnamese_name') or ing_info.get('name_vi', '')
            if 'name' not in item:
                item['name'] = ing_info.get('name') or ing_info.get('name_en', '')

    # ------------------------------------------------------------------
    # Parallel workers
    # ------------------------------------------------------------------

    def _check_conflicts_parallel(
        self,
        dish_name: str,
        cart_items: list,
        extra_ingredients: list
    ) -> Tuple[List[Dict], List[str]]:
        conflict_ingredients = []

        for item in cart_items:
            conflict_ingredients.append({
                'ingredient_id': item.get('ingredient_id'),
                'vietnamese_name': item.get('vietnamese_name') or item.get('name_vi') or item.get('name'),
            })

        for ing in extra_ingredients:
            if isinstance(ing, dict):
                conflict_ingredients.append({
                    'ingredient_id': ing.get('ingredient_id'),
                    'vietnamese_name': ing.get('vietnamese_name') or ing.get('name_vi', '') or ing.get('name', ''),
                })

        conflict_results = self.conflicts.check_conflicts(dish_name, conflict_ingredients)

        conflict_warnings = [
            {
                'message': c.get('message', ''),
                'severity': c.get('severity', 'warning'),
                'source': 'conflict',
                'details': c,
            }
            for c in conflict_results
        ]

        insights = self.conflicts.build_explanations(dish_name, conflict_results)
        return conflict_warnings, insights

    # ------------------------------------------------------------------
    # Misc helpers (preserved from OptimizedShoppingCartPipeline)
    # ------------------------------------------------------------------

    def _get_recipe(self, dish_name: str) -> dict:
        cached = self._recipe_cache.get(dish_name)
        if cached is not None:
            logger.debug(f"Recipe cache HIT for '{dish_name}'")
            return cached

        logger.debug(f"Recipe cache MISS for '{dish_name}' — querying Pinecone")
        recipe = self.kb_service.get_dish_recipe(dish_name)

        if recipe.get('ingredients'):
            self._recipe_cache.set(dish_name, recipe)
            return recipe

        empty = {'ingredients': []}
        self._recipe_cache.set(dish_name, empty)
        return empty

    def _get_suggestions(self, current_ids: list, dish_name: str = "") -> list:
        return self.suggestion_service.get_suggestions(current_ids, dish_name)

    def _normalize_warnings(self, warnings) -> List[Dict[str, object]]:
        normalized: List[Dict[str, object]] = []
        for warning in warnings or []:
            if isinstance(warning, dict):
                message = warning.get('message') or warning.get('text') or ''
                severity = warning.get('severity', 'warning')
                source = warning.get('source', 'model')
                details = {k: v for k, v in warning.items() if k not in {'message', 'text', 'severity', 'source'}}
                normalized.append({'message': message, 'severity': severity, 'source': source, 'details': details})
            else:
                normalized.append({'message': str(warning), 'severity': 'warning', 'source': 'model'})
        return normalized

    def _guardrail_warnings(self, guardrail_info, guardrail_messages=None) -> List[Dict[str, object]]:
        if not guardrail_info:
            return []

        formatted: List[Dict[str, object]] = []
        for entry in guardrail_messages or []:
            if not isinstance(entry, dict):
                continue
            formatted.append({
                'message': entry.get('message', 'Guardrail đã kích hoạt.'),
                'severity': entry.get('severity', 'warning'),
                'source': entry.get('policy_id', 'guardrail'),
            })

        if not formatted:
            codes = guardrail_info.get('violation_codes') or []
            for code in codes:
                formatted.append({
                    'message': f'Guardrail kích hoạt: {code}',
                    'severity': 'warning',
                    'source': 'guardrail',
                })
        return formatted

    @staticmethod
    def _unique_warnings(warnings: List[Dict[str, object]]) -> List[Dict[str, object]]:
        seen = set()
        unique: List[Dict[str, object]] = []
        for warning in warnings:
            key = (warning.get('source'), warning.get('message'))
            if key in seen:
                continue
            seen.add(key)
            unique.append(warning)
        return unique

    def _error_response(
        self,
        error_type: str,
        guardrail_info=None,
        warnings=None,
        dish_name: str = '',
    ) -> dict:
        error_messages = {
            'extraction_failed': 'Không có dữ liệu trích xuất.',
            'guardrail_violation': 'Nội dung vi phạm chính sách an toàn',
            'dish_not_found': 'Không tìm thấy tên món ăn trong yêu cầu',
            'recipe_not_found': f'Không tìm thấy công thức cho món "{dish_name}"',
            'no_valid_ingredients': 'Không có nguyên liệu hợp lệ sau khi xử lý',
        }

        status = 'guardrail_blocked' if error_type == 'guardrail_violation' else 'error'

        return {
            'status': status,
            'error': error_messages.get(error_type, 'Unknown error'),
            'error_type': error_type,
            's3_url': '',
            'dish': {'vietnamese_name': dish_name, 'name': ''},
            'cart': None,
            'suggestions': [],
            'similar_dishes': [],
            'excluded_ingredients': [],
            'warnings': self._unique_warnings(warnings or []),
            'insights': [],
            'guardrail': guardrail_info,
        }

    def get_cache_stats(self) -> Dict[str, object]:
        return {
            'recipe_cache_size': self._recipe_cache.size(),
            'ingredient_id_cache_size': len(self._ingredient_id_cache),
            'ingredient_info_cache_size': len(self._ingredient_info_cache),
            'ingredient_index_size': len(self._ingredient_name_index),
        }

    def clear_caches(self):
        self._recipe_cache.clear()
        self._ingredient_id_cache.clear()
        self._ingredient_info_cache.clear()
        logger.info("All caches cleared")

    def __del__(self):
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)
