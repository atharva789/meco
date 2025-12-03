from meco.workflow import Workflow


def main():
  code = """
def factorial(n: int) -> int:
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)
"""

  meco = Workflow()
  optimized_code, results = meco.iterate(
    num_iterations=3,
    function=code,
  )

  print("Optimized code:\n", optimized_code)
  print("Metrics:", results)


if __name__ == "__main__":
  main()
