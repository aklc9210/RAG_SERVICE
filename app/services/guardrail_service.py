# services/guardrail_service.py
# NEW — local-only guardrail application (replaces AI_service guardrails/policy_handler.py)
# No AWS dependency; applies GuardrailPolicyEvaluator to prompt + response text.

import json
import logging
from typing import Any, Dict, List, Optional

from app.guardrails.policies import GuardrailPolicyEvaluator, GuardrailViolation
from app.utils.json_utils import extract_textual_content

logger = logging.getLogger(__name__)


class GuardrailService:
    """
    Local policy-based guardrail service.
    Replaces PolicyHandler + AWSGuardrailHandler from AI_service.
    """

    def __init__(
        self,
        policy_evaluator: Optional[GuardrailPolicyEvaluator] = None,
        behavior_override: str = '',
    ) -> None:
        self.policy_evaluator = policy_evaluator or GuardrailPolicyEvaluator()
        self.behavior_override = behavior_override.lower()

    def evaluate_input(self, prompt_text: str) -> Optional[Dict[str, Any]]:
        """
        Evaluate raw user input against local policies.
        Returns a guardrail block dict if blocked, else None.
        """
        violations = self.policy_evaluator.evaluate(prompt_text, "")
        if not violations:
            return None

        action = self._resolve_action(violations)
        if action in ('block', 'safe-completion'):
            return {
                'triggered': True,
                'action': action,
                'violation_codes': [f"{v.policy_id}:{v.rule_id}" for v in violations],
                'violations': [v.to_dict() for v in violations],
            }
        return None

    def apply_to_response(
        self,
        prompt_text: str,
        response_text: str,
    ) -> Dict[str, Any]:
        """
        Evaluate a model response against local policies.
        Returns a dict with keys: text (str), guardrail (dict|None), violations (list).
        """
        analysis_text = extract_textual_content(response_text) or response_text
        violations = self.policy_evaluator.evaluate(prompt_text, analysis_text)
        action = self._resolve_action(violations)

        result_text = response_text
        if violations:
            if action in ('block', 'safe-completion'):
                safe = self.policy_evaluator.build_safe_completion(violations)
                result_text = safe
            elif action == 'redact':
                result_text = self.policy_evaluator.redact_text(response_text, violations)

        guardrail_info = None
        if violations:
            guardrail_info = {
                'triggered': True,
                'action': action,
                'violation_codes': [f"{v.policy_id}:{v.rule_id}" for v in violations],
            }

        return {
            'text': result_text,
            'guardrail': guardrail_info,
            'violations': [v.to_dict() for v in violations],
        }

    def _resolve_action(self, violations: List[GuardrailViolation]) -> str:
        if not violations:
            return 'allow'

        actions = {v.action for v in violations}

        if self.behavior_override in {'block', 'redact', 'safe-completion'}:
            override = self.behavior_override
            if override == 'redact' and 'redact' not in actions:
                return 'safe-completion'
            return override

        if 'block' in actions:
            return 'block'
        if 'safe-completion' in actions:
            return 'safe-completion'
        if 'redact' in actions:
            return 'redact'

        return 'allow'
