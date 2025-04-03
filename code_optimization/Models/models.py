from pydantic import BaseModel
from typing import List

class StructuredOutput(BaseModel):
  dependencies: str
  solution_one: str
  solution_two: str
  solution_three: str
  
class TestCase(BaseModel):
  test_file_import: str
  code: str