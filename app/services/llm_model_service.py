# services/llm_model_service.py
# NEW — replaces AI_service/app/services/invoke_model_service.py + bedrock_client.py
# Dish extraction and guardrail pre-check using new LLM client.
# Prompts are preserved from BedrockModelService.

import logging
import os
from typing import Optional

from app.services.llm_client import LLMClient
from app.guardrails.policies import GuardrailPolicyEvaluator
from app.utils.json_utils import parse_json_content

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT_TEMPLATE = """Trích xuất tên món ăn CHÍNH, nguyên liệu THÊM VÀO (hoặc ăn/uống KÈM), và nguyên liệu cần LOẠI TRỪ.

QUY TẮC QUAN TRỌNG:
1. dish_name: Tên món ăn chính người dùng muốn nấu/gọi
2. ingredients: Nguyên liệu THÊM VÀO món ăn, hoặc đồ ăn/uống KÈM THEO (như "ăn kèm", "uống kèm", "chấm với", "vắt vào", "rưới lên")
3. excluded_ingredients: Nguyên liệu cần LOẠI BỎ (dị ứng, không thích, yêu cầu "bỏ", "không có")

Ví dụ:
- "Tôi muốn ăn bún bò Huế với trứng cút"
→ {{"dish_name": "Bún bò Huế", "ingredients": [{{"name": "Trứng cút"}}], "excluded_ingredients": []}}

- "Hướng dẫn nấu món canh cua chua với cam vắt vào"
→ {{"dish_name": "Canh cua chua", "ingredients": [{{"name": "Cam"}}], "excluded_ingredients": []}}

- "Công thức món sầu riêng ăn kèm với rượu"
→ {{"dish_name": null, "ingredients": [{{"name": "Rượu"}}, {{"name": "Sầu riêng"}}], "excluded_ingredients": []}}

- "Làm món trứng chiên ăn kèm sữa đậu nành cho bữa sáng"
→ {{"dish_name": "Trứng chiên", "ingredients": [{{"name": "Sữa đậu nành"}}], "excluded_ingredients": []}}

- "Nấu phở bò"
→ {{"dish_name": "Phở bò", "ingredients": [], "excluded_ingredients": []}}

- "Mình dị ứng đậu phộng, gợi ý topping KHÔNG có hành lá cho phở bò"
→ {{"dish_name": "Phở bò", "ingredients": [], "excluded_ingredients": [{{"name": "Đậu phộng", "reason": "dị ứng"}}, {{"name": "Hành lá", "reason": "người dùng không muốn"}}]}}

- "Cho tôi món phở chay, bỏ hành lá và ngò rí"
→ {{"dish_name": "Phở chay", "ingredients": [], "excluded_ingredients": [{{"name": "Hành lá"}}, {{"name": "Ngò rí"}}]}}

Mô tả: "{description}"

Trả về JSON (chỉ JSON, không giải thích):
{{
    "dish_name": "tên món ăn chính",
    "ingredients": [{{"name": "nguyên liệu thêm/ăn kèm/uống kèm", "unit": "số lượng và đơn vị (VD: 2 củ, 100 g)"}}],
    "excluded_ingredients": [{{"name": "nguyên liệu cần loại trừ", "reason": "lý do (dị ứng/không thích/...)"}}]
}}"""


class LLMModelService:
    """
    Dish name + ingredient extraction using the new LLM client.
    Replaces BedrockModelService from AI_service.

    Also applies local guardrail checks before sending to LLM.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        policy_evaluator: Optional[GuardrailPolicyEvaluator] = None,
    ) -> None:
        self.llm = llm_client or LLMClient()
        self.policy_evaluator = policy_evaluator or GuardrailPolicyEvaluator()

    # ------------------------------------------------------------------
    # Public API (mirrors BedrockModelService interface)
    # ------------------------------------------------------------------

    def extract_dish_name(self, description: str) -> dict:
        """
        Extract dish name, additional ingredients, and excluded ingredients
        from a natural-language description.

        Returns a dict compatible with the old BedrockModelService response:
            {
                dish_name: str | None,
                ingredients: list,
                excluded_ingredients: list,
                guardrail: dict | None,
                guardrail_messages: list,
                warnings: list,
            }
        """
        # Local guardrail pre-check (replaces AWS Bedrock input guardrail)
        guardrail_result = self._check_input_guardrail(description)
        if guardrail_result:
            return guardrail_result

        prompt = _EXTRACT_PROMPT_TEMPLATE.format(description=description)

        try:
            extract_max_tokens = int(os.getenv("EXTRACT_MAX_TOKENS", "256"))
            text = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=extract_max_tokens,
            )
        except Exception as exc:
            logger.error(f"LLM extraction failed: {exc}")
            return {
                "dish_name": None,
                "ingredients": [],
                "excluded_ingredients": [],
                "guardrail": None,
                "guardrail_messages": [],
                "warnings": [{"message": f"LLM extraction error: {exc}", "severity": "error", "source": "system"}],
            }

        parsed = parse_json_content(text)
        return parsed

    def generate_safe_completion(self, user_query: str, violations: list) -> str:
        """
        Generate a polite refusal message for guardrail-blocked requests.
        Uses the LLM to create a context-aware response (replaces SafeCompletionGenerator).
        """
        violation_lines = []
        for v in violations:
            name = v.get('policy_name') or v.get('policy_id', 'policy')
            msg = v.get('message', '')
            violation_lines.append(f"- {name}: {msg}")
        violation_context = "\n".join(violation_lines) if violation_lines else "Nội dung vi phạm chính sách an toàn."

        system_prompt = (
            "Bạn là trợ lý an toàn thực phẩm thân thiện và chuyên nghiệp.\n"
            "Nhiệm vụ: Giải thích tại sao câu hỏi vi phạm chính sách an toàn, "
            "và đề xuất cách tiếp cận an toàn hơn.\n"
            "Quy tắc:\n"
            "- Giọng điệu: Lịch sự, thấu hiểu, không phán xét\n"
            "- Độ dài: 2-3 câu ngắn gọn\n"
            "- KHÔNG lặp lại nội dung nguy hiểm"
        )
        user_prompt = (
            f"Câu hỏi của người dùng: {user_query}\n\n"
            f"Vi phạm phát hiện:\n{violation_context}\n\n"
            "Hãy tạo câu trả lời an toàn, giúp người dùng hiểu vấn đề."
        )

        try:
            return self.llm.chat(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=300,
            )
        except Exception as exc:
            logger.warning(f"Safe completion generation failed: {exc}")
            summary = "; ".join(
                v.get('message', '') for v in violations if v.get('message')
            )
            return f"Xin lỗi, tôi không thể hỗ trợ yêu cầu này vì vi phạm chính sách an toàn: {summary}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_input_guardrail(self, text: str) -> Optional[dict]:
        """
        Run local policy evaluation on raw user input.
        Returns a blocked-response dict if a violation is found, else None.
        """
        violations = self.policy_evaluator.evaluate(text, "")
        if not violations:
            return None

        actions = {v.action for v in violations}
        is_blocked = "block" in actions or "safe-completion" in actions

        violation_dicts = [v.to_dict() for v in violations]
        guardrail_info = {
            "triggered": True,
            "action": "block" if "block" in actions else "safe-completion",
            "violation_codes": [f"{v.policy_id}:{v.rule_id}" for v in violations],
        }

        if is_blocked:
            safe_msg = self.policy_evaluator.build_safe_completion(violations)
            return {
                "dish_name": None,
                "ingredients": [],
                "excluded_ingredients": [],
                "guardrail": guardrail_info,
                "guardrail_messages": violation_dicts,
                "warnings": [],
                "response": safe_msg,
            }

        # Redact only
        return {
            "dish_name": None,
            "ingredients": [],
            "excluded_ingredients": [],
            "guardrail": guardrail_info,
            "guardrail_messages": violation_dicts,
            "warnings": [{"message": v.message, "severity": v.severity, "source": v.policy_id} for v in violations],
        }
