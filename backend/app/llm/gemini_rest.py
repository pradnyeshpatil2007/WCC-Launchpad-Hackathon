"""Gemini REST API request shaping, schema conversion, and response parsing."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ContentPart(BaseModel):
    text: Optional[str] = None
    inline_data: Optional[Dict[str, Any]] = None


class Content(BaseModel):
    role: str = "user"
    parts: List[ContentPart] = Field(default_factory=list)


class LLMRequest(BaseModel):
    purpose: str
    system_instruction: Optional[str] = None
    contents: List[Content]
    json_schema: Optional[Dict[str, Any]] = None
    temperature: float = 0.7
    max_output_tokens: Optional[int] = None
    job_id: str = "_system"


def inline_defs(schema: Dict[str, Any], defs: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively resolve and inline $defs references in JSON schema."""
    if not isinstance(schema, dict):
        return schema

    # If this is a $ref, resolve it
    if "$ref" in schema:
        ref_path = schema["$ref"]
        # e.g., "#/$defs/VisualBeat"
        def_name = ref_path.split("/")[-1]
        if def_name in defs:
            resolved = dict(defs[def_name])
            return inline_defs(resolved, defs)
        return schema

    new_obj = {}
    for k, v in schema.items():
        if k in ("$defs", "definitions"):
            continue
        if isinstance(v, dict):
            new_obj[k] = inline_defs(v, defs)
        elif isinstance(v, list):
            new_obj[k] = [inline_defs(item, defs) if isinstance(item, dict) else item for item in v]
        else:
            new_obj[k] = v
    return new_obj


def to_gemini_schema(raw_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Pydantic v2 JSON Schema to a clean Gemini OpenAPI schema."""
    defs = raw_schema.get("$defs", raw_schema.get("definitions", {}))
    inlined = inline_defs(raw_schema, defs)

    def clean_node(node: Any) -> Any:
        if not isinstance(node, dict):
            return node

        cleaned: Dict[str, Any] = {}
        # Allowed Gemini OpenAPI schema keys
        allowed_keys = {
            "type",
            "format",
            "description",
            "nullable",
            "enum",
            "items",
            "properties",
            "required",
            "minItems",
            "maxItems",
            "minLength",
            "maxLength",
        }

        for k, v in node.items():
            if k in allowed_keys:
                if k == "properties" and isinstance(v, dict):
                    cleaned[k] = {prop_k: clean_node(prop_v) for prop_k, prop_v in v.items()}
                elif k == "items" and isinstance(v, dict):
                    cleaned[k] = clean_node(v)
                elif k == "type" and isinstance(v, list):
                    # Handle ['string', 'null'] -> type: 'string', nullable: True
                    non_null = [t for t in v if t != "null"]
                    cleaned["type"] = non_null[0] if non_null else "string"
                    if "null" in v:
                        cleaned["nullable"] = True
                else:
                    cleaned[k] = v

        # If anyOf / allOf exists, collapse or simplify
        if "anyOf" in node and isinstance(node["anyOf"], list) and len(node["anyOf"]) > 0:
            first = node["anyOf"][0]
            if isinstance(first, dict):
                return clean_node(first)

        return cleaned

    return clean_node(inlined)


def shape_gemini_request(req: LLMRequest) -> Dict[str, Any]:
    """Build the payload for Gemini models.generateContent."""
    body: Dict[str, Any] = {}

    # 1. System instruction
    if req.system_instruction:
        body["systemInstruction"] = {
            "parts": [{"text": req.system_instruction}]
        }

    # 2. Contents
    formatted_contents = []
    for c in req.contents:
        parts = []
        for p in c.parts:
            if p.text is not None:
                parts.append({"text": p.text})
            elif p.inline_data is not None:
                parts.append({"inlineData": p.inline_data})
        formatted_contents.append({"role": c.role, "parts": parts})
    body["contents"] = formatted_contents

    # 3. Generation Config
    gen_config: Dict[str, Any] = {
        "temperature": req.temperature,
    }
    if req.max_output_tokens is not None:
        gen_config["maxOutputTokens"] = req.max_output_tokens

    if req.json_schema is not None:
        gen_config["responseMimeType"] = "application/json"
        gen_config["responseSchema"] = to_gemini_schema(req.json_schema)

    body["generationConfig"] = gen_config
    return body
