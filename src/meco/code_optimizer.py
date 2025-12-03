import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from meco.models import StructuredOutput, TestCase


DEFAULT_MODEL = "gpt-4o-mini"


class CodeOptimizer:
  def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None):
    load_dotenv()
    self.api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not self.api_key:
      raise RuntimeError("OPENAI_API_KEY is required.")
    self.client = OpenAI(api_key=self.api_key)
    self.model = model

  def _call_chat(self, system: str, user: str) -> str:
    response = self.client.chat.completions.create(
      model=self.model,
      response_format={"type": "json_object"},
      temperature=0.4,
      messages=[
        {"role": "system", "content": system},
        {"role": "user", "content": user},
      ],
    )
    return response.choices[0].message.content or "{}"

  def optimize_code(self, code: str) -> Optional[StructuredOutput]:
    system_prompt = (
      "You optimize Python functions for speed and resource efficiency. "
      "Return JSON with keys: dependencies (string of any required imports, empty if none), "
      "solution_one, solution_two, solution_three. "
      "Each solution must keep the same function signature and be runnable as-is."
    )
    payload = self._call_chat(system_prompt, code)
    try:
      data = json.loads(payload)
      return StructuredOutput(**data)
    except Exception as exc:
      print(f"Failed to parse optimizer response: {exc}")
      print(payload)
      return None

  def generate_test_cases(self, code: str) -> Optional[TestCase]:
    system_prompt = (
      "Write unit tests for the provided Python function using unittest. "
      "Return JSON with keys: test_file_import (module import line), and code "
      "containing only the test class definitions (no __main__)."
    )
    payload = self._call_chat(system_prompt, code)
    try:
      data = json.loads(payload)
      return TestCase(**data)
    except Exception as exc:
      print(f"Failed to parse test case response: {exc}")
      print(payload)
      return None
