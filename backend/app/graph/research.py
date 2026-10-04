"""Research Agent implementation with schema validation, repair loop, and tighten feedback (Doc 3 §11)."""

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from pydantic import ValidationError

from app.config import get_settings
from app.core.errors import StageError
from app.domain.script import Script, count_words
from app.llm.gateway import LLMGateway
from app.llm.gemini_rest import Content, ContentPart, LLMRequest


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def get_system_prompt() -> str:
    prompt_file = PROMPTS_DIR / "research_system.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return "You are an expert educator producing a 120-140 word vertical educational video script in JSON."


class ResearchAgent:
    """Agent that creates structured, word-budgeted video scripts from topics."""

    def __init__(self, gateway: Optional[LLMGateway] = None):
        self.gateway = gateway or LLMGateway()
        self.settings = get_settings()

    async def execute(
        self,
        prompt: str = "",
        topic: str = "",
        job_id: str = "_system",
        tighten_feedback: Optional[str] = None,
        script_feedback: Optional[str] = None,
        event_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Script:
        return await self.generate_script(
            topic=prompt or topic,
            job_id=job_id,
            script_feedback=tighten_feedback or script_feedback,
            event_callback=event_cb or event_callback,
        )

    async def generate_script(
        self,
        topic: str,
        job_id: str = "_system",
        script_feedback: Optional[str] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Script:
        """Generate a validated Script with self-correction repair loop."""
        system_prompt = get_system_prompt()
        schema = Script.model_json_schema()

        # Build initial prompt
        user_prompt = f"Please research and write a complete 60-second educational video script on this topic:\n<topic>\n{topic.strip()}\n</topic>"
        if script_feedback:
            user_prompt += f"\n\nIMPORTANT TIGHTEN FEEDBACK:\n{script_feedback}"

        history: list[Content] = [
            Content(role="user", parts=[ContentPart(text=user_prompt)])
        ]

        last_error = ""
        for attempt in range(1, self.settings.SCRIPT_MAX_REPAIR_ATTEMPTS + 1):
            req = LLMRequest(
                purpose="research" if attempt == 1 else "script_repair",
                system_instruction=system_prompt,
                contents=history,
                json_schema=schema,
                temperature=self.settings.LLM_TEMPERATURE_RESEARCH,
                job_id=job_id,
            )

            if attempt > 1 and event_callback:
                event_callback(
                    "retry.attempt",
                    {
                        "node": "research",
                        "attempt": attempt,
                        "maxAttempts": self.settings.SCRIPT_MAX_REPAIR_ATTEMPTS,
                        "message": "Refining the script",
                    },
                )

            result = await self.gateway.generate(req)

            # Try validating output
            if result.parsed:
                try:
                    script = Script.model_validate(result.parsed)
                    return script
                except ValidationError as ve:
                    err_msgs = [f"- {err['loc']}: {err['msg']}" for err in ve.errors()]
                    err_summary = "\n".join(err_msgs)

                    # Extract current word count for precise repair guidance
                    raw_text = ""
                    for s in result.parsed.get("scenes", []):
                        for b in s.get("beats", []):
                            raw_text += " " + b.get("narration", "")
                    current_words = count_words(raw_text)

                    last_error = f"Total words: {current_words}. Errors:\n{err_summary}"

                    repair_msg = (
                        f"Your output failed validation:\n{err_summary}\n"
                        f"Current total word count is {current_words} words (target is strictly 120-140 words).\n"
                        f"Please return the complete corrected script matching the JSON schema."
                    )

                    # Append model response and repair message to conversation history
                    history.append(Content(role="model", parts=[ContentPart(text=result.text)]))
                    history.append(Content(role="user", parts=[ContentPart(text=repair_msg)]))
            else:
                last_error = f"Model did not return valid JSON: {result.text[:200]}"
                history.append(Content(role="model", parts=[ContentPart(text=result.text)]))
                history.append(
                    Content(
                        role="user",
                        parts=[ContentPart(text="Output must be valid JSON matching the schema. Please output the JSON object only.")],
                    )
                )

        raise StageError(
            code="RESEARCH_FAILED",
            stage="research",
            message=f"Script failed validation after {self.settings.SCRIPT_MAX_REPAIR_ATTEMPTS} attempts: {last_error}",
            retryable=True,
        )
