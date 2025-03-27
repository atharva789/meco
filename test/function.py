 
import unittest
from functools import reduce
import operator

def factorial(n):
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    if n == 0:
        return 1
    return reduce(operator.mul, range(1, n + 1), 1)
        
{
  "lamda_func_inputs": [
    {
      "input_value": "0",
      "data_type": "int"
    },
    {
      "input_value": "1",
      "data_type": "int"
    },
    {
      "input_value": "5",
      "data_type": "int"
    },
    {
      "input_value": "10",
      "data_type": "int"
    }
  ],
  "expected_outputs": "[1, 1, 120, 3628800]"
}
        