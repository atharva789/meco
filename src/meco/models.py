from typing import Optional

from pydantic import BaseModel


class StructuredOutput(BaseModel):
  dependencies: Optional[str] = None
  solution_one: str
  solution_two: str
  solution_three: str


class TestCase(BaseModel):
  test_file_import: str
  code: str
