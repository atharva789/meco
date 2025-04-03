from google import genai
import os
import json
from dotenv import load_dotenv
from code_optimization.Models.models import StructuredOutput, TestCase

load_dotenv()
  
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
    Write a test-case class using the python 'unittest' library for the given function. 
    The function lies in 'solutions.py', so imports should follow the style
    'from solutions import ##replace/w/function_name'. Do not write "if __name__ == '__main__'", class only.
    Write code-only
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
      try:
        json_data = json.loads(response.text)
        validated_data = TestCase(**json_data)
        return validated_data
      except json.JSONDecodeError:
        print("""
Code Optimizer Agent:
    failed to create TestCase class""")
        return response.text
    #xceptions to handle: APIConnectionError, RateLimitError, APIStatusError
    except Exception as e:
      print(f"Error with Gemini + test-case generation: {e}")
    
  
  