# utils/json_utils.py
# Adapted from AI_service/app/utils/json_utils.py
# Change: removed read_json_from_s3_uri (boto3/S3 dependency dropped)
import json
from typing import Dict, Any, Optional

__all__ = [
    "parse_json_content",
    "extract_textual_content",
    "extract_prompt_from_body",
]


def parse_json_content(content: str) -> dict:
    if content.startswith('```'):
        content = '\n'.join(content.split('\n')[1:-1]).lstrip('json')

    try:
        data = json.loads(content)
    except Exception:
        fallback_warning = 'Kết quả mô hình không phải JSON hợp lệ.'
        return {
            "dish_name": None,
            "ingredients": [],
            "warnings": [fallback_warning],
            "response": content.strip() if isinstance(content, str) else None,
        }

    dish_name = data.get('dish_name')
    ingredients = data.get('ingredients', []) if isinstance(data.get('ingredients', []), list) else []
    excluded_ingredients = data.get('excluded_ingredients', []) if isinstance(data.get('excluded_ingredients', []), list) else []
    warnings = data.get('warnings', []) if isinstance(data.get('warnings'), list) else []
    response_text = data.get('response') if isinstance(data.get('response'), str) else None

    return {
        "dish_name": dish_name,
        "ingredients": ingredients,
        "excluded_ingredients": excluded_ingredients,
        "warnings": warnings,
        "response": response_text,
        "violations": data.get('violations') if isinstance(data.get('violations'), list) else [],
    }


def extract_textual_content(raw_text: str) -> str:
    try:
        data = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        return raw_text

    texts = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            texts.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                _walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(data)
    return '\n'.join(texts) if texts else raw_text


def extract_prompt_from_body(body: str) -> str:
    if not body:
        return ''

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return ''

    prompt_parts = []
    if isinstance(payload, dict):
        if isinstance(payload.get('prompt'), str):
            prompt_parts.append(payload['prompt'])

        messages = payload.get('messages')
        if isinstance(messages, list):
            for message in messages:
                content = message.get('content') if isinstance(message, dict) else None
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get('type') == 'text':
                            text = part.get('text')
                            if text:
                                prompt_parts.append(text)
                elif isinstance(content, str):
                    prompt_parts.append(content)

    return '\n'.join(prompt_parts)
