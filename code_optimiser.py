from typing import List, Dict
from google import genai
from google.genai.types import GenerationConfig
from google.genai import types
import os
import json
from pydantic import BaseModel
from pyparser import CodeParser
from dotenv import load_dotenv

load_dotenv()

class StructuredOutput(BaseModel):
  dependencies: str
  solution_one: str
  solution_two: str
  solution_three: str
  unit_tests: List[str]
  
class FunctionInputFormat(BaseModel):
  input_value: str
  data_type: str 
  
class TestCase(BaseModel):
  lamda_func_inputs: List[FunctionInputFormat]
  expected_outputs: str
  
  
class CodeOptimizer:
  def __init__(self):
    self.gemini_api_key = os.getenv("GEMINI_API_KEY")
    self.client = genai.Client(api_key=self.gemini_api_key)

  def optimize_code(self, code: str):
    sys_instruct = "you are optimising a provided code function. You will read a piece of code and output an optimised version of this code on every performance metric. Generate 3 unique optimised code solutions with the same function name as provided. Provide all imports or dependencies, and generate unit-tests. Don't give an explanation, only code."
    prompt = code
    
    try:
      response = self.client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config={
           'response_mime_type':'application/json',
           'response_schema': StructuredOutput,
            'system_instruction': sys_instruct
         }
      )
      response_text = response.text
      try:
        json_data = json.loads(response_text)
        validated_data = StructuredOutput(**json_data)
        return validated_data
      except json.JSONDecodeError:
        return json_data
    #xceptions to handle: APIConnectionError, RateLimitError, APIStatusError
    except Exception as e:
      print(f"An unexpected error occurred: {e}")
  
  def generate_test_cases(self, code: str) -> str:
    sys_instruct = """
    Generate test-cases with inputs that will be fed to the test-function.
    Write a test-case class using the  python 'unittest' library. 
    code-only
    """
    prompt = code    
    try:
      response = self.client.models.generate_content(
      model="gemini-2.0-flash",
      contents=prompt,
      config={
        'response_mime_type':'application/json',
        'response_schema': TestCase,
        'system_instruction': sys_instruct
      }
      )
      return response.text
    #xceptions to handle: APIConnectionError, RateLimitError, APIStatusError
    except Exception as e:
      print(f"An unexpected error occurred: {e}")
    
  
  