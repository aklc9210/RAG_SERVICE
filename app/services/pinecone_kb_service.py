# services/pinecone_kb_service.py
# NEW — replaces AI_service/app/services/bedrock_kb_service.py
# Uses Pinecone retrieval (from rag_service/retrieval/) + new LLM to generate recipe JSON.
# The retrieval query, context assembly, and recipe JSON generation prompt are preserved
# from BedrockKBService; only the retrieval backend and LLM invocation are replaced.

import json
import logging
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Ensure project root is importable (rag_service root)
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent.parent  # rag_service/
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


_SHARED_LOCK = threading.Lock()
_SHARED_RETRIEVER = None


_RECIPE_SYSTEM_PROMPT = """Bạn là chuyên gia ẩm thực Việt Nam. Nhiệm vụ của bạn là trích xuất thông tin công thức món ăn từ tài liệu được cung cấp.

QUAN TRỌNG:
- Chỉ trả về JSON hợp lệ, KHÔNG giải thích thêm
- Trích xuất TỐI ĐA 25 nguyên liệu CHÍNH từ tài liệu
- Ưu tiên nguyên liệu theo thứ tự importance:
  * importance=3: Nguyên liệu CHÍNH tạo nên đặc trưng món (BẮT BUỘC phải có)
  * importance=2: Nguyên liệu QUAN TRỌNG (gia vị chính, nước sốt) (ưu tiên cao)
  * importance=1: Nguyên liệu phụ (chỉ lấy nếu còn slot trong 25 nguyên liệu)
- TUYỆT ĐỐI không bỏ sót nguyên liệu có importance >= 2
- Nếu có nhiều hơn 25 nguyên liệu, chỉ giữ lại 25 nguyên liệu quan trọng nhất
- vietnamese_name: tên tiếng Việt của món ăn hoặc nguyên liệu
- name: tên tiếng Anh của món ăn hoặc nguyên liệu
- unit: kết hợp số lượng và đơn vị (VD: "500 g", "2 củ", "1 muỗng canh"), để rỗng nếu không có
- danh sách nguyên liệu không được trùng lặp"""

_RECIPE_USER_PROMPT_TEMPLATE = """Dựa trên các tài liệu sau, hãy trích xuất công thức cho món: {dish_name}

{context}

Trả về JSON với format (tối đa 25 nguyên liệu quan trọng nhất):
{{"vietnamese_name": "tên món tiếng Việt", "name": "tên món tiếng Anh", "ingredients": [{{"vietnamese_name": "tên nguyên liệu tiếng Việt", "name": "tên nguyên liệu tiếng Anh", "unit": "số lượng và đơn vị"}}]}}"""


def _clean_json_answer(answer: str) -> str:
    """Strip markdown fences and fix trailing commas."""
    if '```' in answer:
        buf, in_code = [], False
        for line in answer.splitlines():
            if '```' in line:
                in_code = not in_code
                continue
            if in_code:
                buf.append(line)
        answer = "\n".join(buf).strip()

    json_start = answer.find('{')
    json_end = answer.rfind('}')
    if json_start >= 0 and json_end > json_start:
        answer = answer[json_start:json_end + 1]
    elif json_start >= 0:
        answer = answer[json_start:]
        open_braces = answer.count('{')
        close_braces = answer.count('}')
        open_brackets = answer.count('[')
        close_brackets = answer.count(']')
        if open_brackets > close_brackets:
            answer += '\n' + (']' * (open_brackets - close_brackets))
        if open_braces > close_braces:
            answer += '\n' + ('}' * (open_braces - close_braces))

    answer = re.sub(r',(\s*[}\]])', r'\1', answer)
    return answer


class PineconeKBService:
    """
    Dish recipe retrieval using Pinecone dense search + LLM recipe generation.
    Replaces BedrockKBService from AI_service.

    Retrieval flow:
      1. Embed query with multilingual-e5 (same model used at ingestion)
      2. Search Pinecone index with type='dish' filter
      3. Assemble top-K documents as context
      4. Call LLM to extract structured recipe JSON

    The recipe JSON format and prompt are preserved from BedrockKBService.
    """

    def __init__(
        self,
        llm_client=None,
        retriever=None,
    ) -> None:
        self._llm = llm_client
        self._retriever = retriever  # lazy-initialised on first use
        self._init_done = False

    def _ensure_init(self) -> None:
        if self._init_done:
            return

        if self._llm is None:
            from app.services.llm_client import LLMClient
            self._llm = LLMClient()

        if self._retriever is None:
            self._retriever = _build_retriever()

        self._init_done = True

    # ------------------------------------------------------------------
    # Public API (mirrors BedrockKBService)
    # ------------------------------------------------------------------

    def get_dish_recipe(self, dish_name: str) -> dict:
        """
        Retrieve and generate a structured recipe for the given dish name.

        Returns dict compatible with OptimizedShoppingCartPipeline expectations:
            {
                vietnamese_name: str,
                name: str,
                ingredients: [{ vietnamese_name, name, unit }],
                prep_time: str | None,
                servings: int | None,
            }
        """
        self._ensure_init()

        recipe_top_k = int(os.getenv("RECIPE_TOP_K", "5"))
        recipe_context_chars = int(os.getenv("RECIPE_CONTEXT_CHARS", "350"))
        recipe_max_tokens = int(os.getenv("RECIPE_MAX_TOKENS", "768"))

        query = f"Tìm đúng món: {dish_name}"
        try:
            raw_results = self._retriever.search_filtered(
                query_text=query,
                top_k=recipe_top_k,
                type_filter="dish",
            )
        except Exception as exc:
            logger.error(f"Pinecone retrieval error for '{dish_name}': {exc}")
            return {"vietnamese_name": dish_name, "name": "", "ingredients": []}

        if not raw_results:
            logger.info(f"No Pinecone results for dish '{dish_name}'")
            return {"vietnamese_name": dish_name, "name": "", "ingredients": []}

        # Build context from retrieved documents (same approach as BedrockKBService)
        context_parts = []
        for idx, result in enumerate(raw_results[:recipe_top_k], 1):
            text = result.get("text", "")
            if text:
                context_parts.append(f"[Tài liệu {idx}]:\n{text[:recipe_context_chars]}")
        context = "\n\n".join(context_parts)

        user_prompt = _RECIPE_USER_PROMPT_TEMPLATE.format(
            dish_name=dish_name,
            context=context,
        )

        try:
            answer = self._llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=_RECIPE_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=recipe_max_tokens,
            )
        except Exception as exc:
            logger.error(f"LLM recipe generation failed for '{dish_name}': {exc}")
            return {"vietnamese_name": dish_name, "name": "", "ingredients": []}

        if not answer:
            return {"vietnamese_name": dish_name, "name": "", "ingredients": []}

        answer = _clean_json_answer(answer)

        try:
            parsed = json.loads(answer)
        except Exception:
            logger.warning(f"Could not parse recipe JSON for '{dish_name}': {answer[:200]}")
            return {"vietnamese_name": dish_name, "name": "", "ingredients": []}

        if not isinstance(parsed, dict) or "ingredients" not in parsed:
            return {"vietnamese_name": dish_name, "name": "", "ingredients": []}

        cleaned_ingredients = []
        for it in parsed.get("ingredients", []):
            if not isinstance(it, dict):
                continue
            vi_name = it.get("vietnamese_name") or it.get("name_vi")
            en_name = it.get("name") or it.get("name_en", "")
            if not vi_name or not str(vi_name).strip():
                continue
            cleaned_ingredients.append({
                "vietnamese_name": str(vi_name).strip(),
                "name": str(en_name).strip() if en_name else "",
                "unit": it.get("unit", ""),
            })

        return {
            "vietnamese_name": parsed.get("vietnamese_name") or dish_name,
            "name": parsed.get("name") or "",
            "ingredients": cleaned_ingredients,
        }


# ---------------------------------------------------------------------------
# Factory helper: build a Retriever connected to Pinecone
# ---------------------------------------------------------------------------

def _build_retriever():
    """Build and return a Retriever instance connected to the Pinecone index."""
    from pinecone import Pinecone
    from ingestion.embedding import EmbeddingModel
    from retrieval.retriever import Retriever

    global _SHARED_RETRIEVER
    reuse_shared = os.getenv("REUSE_SHARED_RETRIEVER", "1") not in {"0", "false", "False"}
    if reuse_shared and _SHARED_RETRIEVER is not None:
        return _SHARED_RETRIEVER

    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "vn-food-rag")
    if not api_key:
        raise EnvironmentError("PINECONE_API_KEY is not set in the environment.")

    with _SHARED_LOCK:
        if reuse_shared and _SHARED_RETRIEVER is not None:
            return _SHARED_RETRIEVER

        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        embedding_model = EmbeddingModel()
        retriever = Retriever(embedding_model=embedding_model, pinecone_index=index)
        if reuse_shared:
            _SHARED_RETRIEVER = retriever
        return retriever
