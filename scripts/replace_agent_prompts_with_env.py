"""
One-off migration: replace the huge hardcoded get_assistant_system_prompt() function
with an environment-variable based loader.

This script is safe to run from ANY working directory.

Usage:
  - From repo root:
      python backend/scripts/replace_agent_prompts_with_env.py
  - From backend/:
      python scripts/replace_agent_prompts_with_env.py
"""

from __future__ import annotations

from pathlib import Path
import re


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
TARGET = BACKEND_DIR / "app" / "services" / "openai_service.py"


NEW_FUNC = r'''    def get_assistant_system_prompt(self, assistant_id: AssistantType) -> str:
        """
        Load the assistant system prompt from environment variables.

        Supported configuration:
          - Inline env var:        AGENT_PROMPT_<ASSISTANT>
          - File path env var:     AGENT_PROMPT_<ASSISTANT>_PATH

        Optional global prefix applied to all assistants:
          - Inline env var:        AGENT_PROMPT_BASE
          - File path env var:     AGENT_PROMPT_BASE_PATH

        Assistants (derived from AssistantType values):
          - TYPEX
          - REFERENCES
          - ACADEMIC_REFERENCES
          - THERAPY_GPT
          - WHATS_TRENDY
          - COURSE
        """
        suffix = _assistant_env_suffix(assistant_id)
        prompt_key = f"AGENT_PROMPT_{suffix}"

        base_prompt = _load_prompt_from_env_or_file("AGENT_PROMPT_BASE")
        prompt = _load_prompt_from_env_or_file(prompt_key)

        if not prompt:
            logger.error(f"❌ Missing/empty agent prompt: {prompt_key} (or {prompt_key}_PATH)")
            raise ValueError(f"Missing/empty environment variable: {prompt_key}")

        full = f"{base_prompt}\n\n{prompt}" if base_prompt else prompt
        logger.info(f"🧩 Loaded agent prompt: {prompt_key} (len={len(full)})")
        return full
'''


def main() -> None:
    if not TARGET.exists():
        raise SystemExit(f"Target file not found: {TARGET}")

    text = TARGET.read_text(encoding="utf-8")

    # Replace from "def get_assistant_system_prompt" up to (but not including) "async def generate_chat_response("
    pattern = re.compile(
        r"(?ms)^\s{4}def get_assistant_system_prompt\(self, assistant_id: AssistantType\) -> str:\n"
        r".*?"
        r"^\s{4}async def generate_chat_response\(",
    )

    m = pattern.search(text)
    if not m:
        raise SystemExit("Could not find function boundaries to replace.")

    replacement = NEW_FUNC + "    async def generate_chat_response("
    new_text = pattern.sub(replacement, text, count=1)

    TARGET.write_text(new_text, encoding="utf-8")
    print("✅ Replaced get_assistant_system_prompt() with env-based loader")


if __name__ == "__main__":
    main()

