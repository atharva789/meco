import docker.errors
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import docker
import io
import json
import tarfile

from meco.code_optimizer import CodeOptimizer
from meco.models import TestCase

# Tuning parameters for the search and measurement loops.
DEFAULT_MAX_DEPTH = 3
MIN_IMPROVEMENT = 1e-3
RUNS_PER_CANDIDATE = 3


@dataclass
class Candidate:
  code: str
  metrics: Dict[str, float]
  depth: int
  dependencies: Optional[str] = None
  lineage: List[str] = field(default_factory=list)


class Workflow:
  def __init__(self):
    self.optimizer_agent = CodeOptimizer()
    print("Initializing Docker…")
    self.docker_client = docker.from_env()
    self.container_name = "python-code-executor"
    self.docker_container = self._ensure_container()
    print("Docker setup completed.")

  def _ensure_container(self):
    try:
      container = self.docker_client.containers.get(self.container_name)
    except docker.errors.NotFound:
      container = self.docker_client.containers.run(
        "python:3.9-slim",
        detach=True,
        name=self.container_name,
        tty=True,
      )
      container.exec_run("mkdir -p /test")
    except docker.errors.APIError as e:
      print(f"Error while initializing docker for code execution: {e}")
      raise
    return container

  def _validate_test_cases(self, raw: str) -> Optional[TestCase]:
    try:
      json_data = json.loads(raw)
      return TestCase(**json_data)
    except Exception as e:
      print(f"Error while validating test-cases: {e}")
      return None

  def _write_files_to_container(self, files: Dict[str, str], container_dir: str) -> bool:
    """Write files into the running container using a tar stream."""
    try:
      tar_stream = io.BytesIO()
      with tarfile.open(fileobj=tar_stream, mode="w") as tar:
        for filename, content in files.items():
          data = content.encode("utf-8")
          tarinfo = tarfile.TarInfo(name=filename)
          tarinfo.size = len(data)
          tar.addfile(tarinfo, io.BytesIO(data))
      tar_stream.seek(0)
      self.docker_container.put_archive(container_dir, tar_stream.getvalue())
      return True
    except Exception as e:
      print(f"Error while copying files into Docker container: {e}")
      return False

  def _build_test_harness(self, test_cases: TestCase, runs: int) -> str:
    """
    Builds a deterministic test harness that:
      - imports the generated solutions
      - runs the LLM-provided unittest code
      - aggregates runtime/memory/CPU metrics over several runs
      - prints a single JSON line that get_metrics parses
    """
    user_tests = test_cases.code.strip()
    if "import unittest" not in user_tests:
      user_tests = "import unittest\n" + user_tests

    import_line = test_cases.test_file_import.strip() or "from solutions import *"

    harness = f"""
import io
import json
import resource
import sys
import time
import unittest
{import_line}

{user_tests}


def _load_suite():
  return unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])


def _run_once():
  suite = _load_suite()
  buffer = io.StringIO()
  runner = unittest.TextTestRunner(stream=buffer, verbosity=0)
  wall_start = time.perf_counter()
  cpu_start = time.process_time()
  result = runner.run(suite)
  cpu_end = time.process_time()
  wall_end = time.perf_counter()
  usage = resource.getrusage(resource.RUSAGE_SELF)
  return {{"runtime": wall_end - wall_start, "cpu": cpu_end - cpu_start, "memory": float(usage.ru_maxrss), "ok": result.wasSuccessful()}}


def main():
  results = []
  for _ in range({runs}):
    results.append(_run_once())
  aggregates = {{"runtime": 0.0, "cpu": 0.0, "memory": 0.0, "ok": all(item["ok"] for item in results)}}
  for item in results:
    aggregates["runtime"] += item["runtime"]
    aggregates["cpu"] += item["cpu"]
    aggregates["memory"] += item["memory"]
  aggregates["runtime"] /= {runs}
  aggregates["cpu"] /= {runs}
  aggregates["memory"] /= {runs}
  print(json.dumps(aggregates))


if __name__ == "__main__":
  main()
"""
    return harness

  def _prepare_test_cases(self, function: str, test_cases: Optional[str]) -> Optional[TestCase]:
    if test_cases is None:
      generated = self.optimizer_agent.generate_test_cases(code=function)
      if isinstance(generated, TestCase):
        return generated
      return None
    return self._validate_test_cases(test_cases)

  def get_metrics(self, function: str, test_cases: Optional[TestCase], dependencies: Optional[str] = None) -> Dict[str, float]:
    """
    Writes the candidate solution and tests into the container, executes them,
    and returns averaged runtime/cpu/memory metrics.
    """
    if test_cases is None:
      raise ValueError("Test cases are required to measure a candidate.")

    solution_preamble = (dependencies or "").strip()
    if solution_preamble:
      solution_preamble += "\n\n"
    solution_body = f"{solution_preamble}{function.strip()}\n"

    test_harness = self._build_test_harness(test_cases, runs=RUNS_PER_CANDIDATE)
    files = {"solutions.py": solution_body, "tests.py": test_harness}
    docker_write_status = self._write_files_to_container(files=files, container_dir="/test")
    if not docker_write_status:
      return {"runtime": float("inf"), "cpu": float("inf"), "memory": float("inf"), "ok": False}

    try:
      res = self.docker_container.exec_run(cmd=["python", "tests.py"], workdir="/test", demux=True)
      stdout, stderr = res.output
      output = (stdout or b"").decode("utf-8").strip()
      if stderr:
        print(f"Container stderr: {(stderr or b'').decode('utf-8')}")
      metric_line = output.splitlines()[-1] if output else "{}"
      metrics = json.loads(metric_line)
      if not isinstance(metrics, dict):
        raise ValueError("Unexpected metrics payload")
      return metrics
    except docker.errors.APIError as e:
      print(f"A Docker error occurred: {e}")
    except Exception as e:
      print(f"Error while collecting metrics: {e}")
    return {"runtime": float("inf"), "cpu": float("inf"), "memory": float("inf"), "ok": False}

  def _score(self, metrics: Dict[str, float]) -> float:
    # Lower is better; memory is scaled down to avoid dwarfing runtime.
    return metrics.get("runtime", float("inf")) + metrics.get("cpu", 0.0) + (metrics.get("memory", 0.0) * 1e-6)

  def _improvement(self, previous: Dict[str, float], candidate: Dict[str, float]) -> float:
    return self._score(previous) - self._score(candidate)

  def _select_best(self, candidates: List[Candidate]) -> Candidate:
    return min(candidates, key=lambda c: self._score(c.metrics))

  def iterate(self, num_iterations: int, function: str, test_cases: Optional[str] = None, max_depth: int = DEFAULT_MAX_DEPTH, epsilon: float = MIN_IMPROVEMENT) -> Tuple[str, Dict[str, float]]:
    """
    Performs tree-based exploration with forward selection:
      - Expand the current best node into multiple children via the LLM.
      - Evaluate each child, pick the best, and continue down that branch.
      - Stop when depth is reached or the gain is below epsilon.
    """
    depth_limit = min(max_depth, DEFAULT_MAX_DEPTH, max(1, num_iterations))
    prepared_tests = self._prepare_test_cases(function, test_cases)
    if prepared_tests is None:
      raise ValueError("No valid test cases were provided or generated.")
    baseline_metrics = self.get_metrics(function, prepared_tests)
    best = Candidate(code=function, metrics=baseline_metrics, depth=0, lineage=["root"])

    for depth in range(depth_limit):
      variants = self.optimizer_agent.optimize_code(best.code)
      if variants is None:
        break

      dependencies = getattr(variants, "dependencies", None)
      children = [
        Candidate(code=variants.solution_one, metrics={}, depth=depth + 1, dependencies=dependencies, lineage=best.lineage + ["solution_one"]),
        Candidate(code=variants.solution_two, metrics={}, depth=depth + 1, dependencies=dependencies, lineage=best.lineage + ["solution_two"]),
        Candidate(code=variants.solution_three, metrics={}, depth=depth + 1, dependencies=dependencies, lineage=best.lineage + ["solution_three"]),
      ]

      for child in children:
        child.metrics = self.get_metrics(child.code, prepared_tests, dependencies=child.dependencies)

      next_best = self._select_best(children)
      gain = self._improvement(best.metrics, next_best.metrics)
      print(f"Depth {depth + 1}: best score improvement {gain}")

      if gain <= epsilon:
        print("Epsilon convergence reached; stopping search.")
        break

      best = next_best

    return best.code, best.metrics
