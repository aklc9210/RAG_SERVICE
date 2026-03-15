"""
Request Processor — business-logic handler for RAG Service.
Adapted from AI_service/app/rabbitmq/processor.py.

Changes:
  - Uses ShoppingCartPipeline (Pinecone + LLM) instead of OptimizedShoppingCartPipeline
  - S3ImageService removed (image processing not in scope)
  - text-only flow preserved exactly
"""
import json
import logging
import time
import os
from typing import Dict, Any

from app.pipeline import ShoppingCartPipeline
from app.schemas import RecipeAnalysisRequest, RecipeAnalysisResponse

logger = logging.getLogger(__name__)


class RecipeAnalysisProcessor:

    def __init__(self):
        """Initialize processor with pipeline."""
        try:
            cache_ttl = int(os.getenv('RECIPE_CACHE_TTL', '3600'))
            max_workers = int(os.getenv('OPTIMIZED_MAX_WORKERS', '3'))

            self.pipeline = ShoppingCartPipeline(
                max_workers=max_workers,
                recipe_cache_ttl=cache_ttl,
            )
            logger.info(
                f"RecipeAnalysisProcessor initialized "
                f"(TTL={cache_ttl}s, Workers={max_workers})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize RecipeAnalysisProcessor: {e}", exc_info=True)
            raise

    def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Processing request: {json.dumps(request_data, ensure_ascii=False)[:200]}")

        try:
            # Validate with Pydantic
            try:
                request = RecipeAnalysisRequest(**request_data)
            except Exception as e:
                logger.error(f"Request validation error: {e}")
                return {
                    "success": False,
                    "error": f"Invalid request format: {str(e)}",
                    "error_type": "validation_error",
                }

            user_input = request.user_input or request.description

            if not user_input:
                return {
                    "success": False,
                    "error": "Vui lòng cung cấp user_input hoặc description",
                    "error_type": "missing_input",
                }

            logger.info(f"Processing text input: {user_input[:100]}...")
            result = self.pipeline.process(user_input)

            # Validate response shape with Pydantic
            try:
                response = RecipeAnalysisResponse(**result)
                response_dict = response.model_dump()
            except Exception as e:
                logger.error(f"Response validation error: {e}")
                return {
                    "success": False,
                    "error": f"Response validation error: {str(e)}",
                    "error_type": "response_validation_error",
                    "result": result,
                }

            elapsed_ms = int((time.time() - start_time) * 1000)
            response_dict['processing_time_ms'] = elapsed_ms

            status = response_dict.get('status', 'error')
            if status == 'success':
                logger.info(f"Request processed successfully in {elapsed_ms}ms")
                return {"success": True, "result": response_dict}
            else:
                error_msg = response_dict.get('error', f"Processing failed with status: {status}")
                logger.warning(f"Request processing failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": status,
                    "result": response_dict,
                }

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Unexpected error in process_request: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Unexpected processing error: {str(e)}",
                "error_type": "unexpected_error",
                "processing_time_ms": elapsed_ms,
            }
