import docker.errors
from code_optimization.code_optimiser import CodeOptimizer
from typing import Optional, List
import tarfile
import io
import os
import docker
import json
import time
from code_optimization.Models.models import TestCase

class Workflow:
  def __init__(self):
    self.optimizer_agent = CodeOptimizer()
    print("Initializing Docker…")
    #docker settings
    # self.docker_init = docker.DockerClient(base_url="unix://var/run/docker.sock")
    self.docker_client = docker.from_env()
    self.container_name = 'python-code-executor'
    try:
      self.docker_container = self.docker_client.containers.get(self.container_name)
    except docker.errors.NotFound:
      self.docker_container = self.docker_client.containers.run(
        'python:3.9-slim', 
        detach=True,
        name=self.container_name,
        tty=True 
          )
      self.docker_container.exec_run("apt-get update && apt-get install -y time")
      self.docker_container.exec_run(['mkdir', 'test'])
    except docker.errors.APIError as e:
      print(f"Error while initializing docker for code execution: {e}")
    print("Docker setup completed.")
    #test to ensure docker-api is working
    # print(self.docker_client.containers.run("alpine", ["echo", "hello", "world"]))
  
  def validate_test_cases(self, test_cases: str) -> Optional[TestCase]:
    try:
      json_data = json.loads(test_cases)
      validated_cases = TestCase(**json_data)
      return validated_cases
    except Exception as e:
      print(f"Error while validating test-cases: {e}")
      return None
  
  def write_file_to_container(self, file_content: dict, container_dir: str) -> bool:
    """
    this method will be used to copy all 3 solutions into a single file in the docker container,
    then be used to write test-cases into another directory.

    Args:
        file_content (dict): {
          code: str,
          test_code: str
        }
        container_dir (str): where the test function and test_code will be stored inside the docker container

    Returns:
        bool: True is written, False otherwise
    """
    try:
      for key, value in file_content.items():
        res = self.docker_container.exec_run(f"echo '{value}' > {container_dir}/{key}.py")
        print(f"  write_file_to_container: {res}")
      return True
    except Exception as e:
      print(f"Error while copying file into Docker-conatiner: {e}")
      
      return False
    
  def get_metrics(self, function: str, test_cases: Optional[List[str]]): #test-cases or test-data required to actually time the function    
    try:
      test_code = f"""
import psutil, time, threading

{test_cases.code}

def monitor(interval, stop_event):
  #no GPU monitoring yet
  highest_cpu, highest_mem, highest_io = -1.0, -2.0, -3.0
  start_time = time.time()
  while not stop_event.is_set():
    cpu = psutil.cpu_percent(interval=interval)
    mem = psutil.virtual_memory().percent
    
    if cpu > highest_cpu:
      highest_cpu = cpu
    if mem > highest_mem:
      highest_mem = mem
      
    time.sleep(0.00005) #to avoid overlapping measurements
  endtime = time.time()
  runtime = end_time - start_time
  return f"{{highest_cpu}},{{highest_mem}},{{runtime}}"
  
  
stop_event = threading.Event()
monitor_thread = threading.Thread(target=monitor, args=(0.000005, stop_event))

if __name__ == '__main__':
  monitor_thread.start()
  unittest.main()
  
  stop_event.set()
  monitor_thread.join()
      """
      file_content: dict = {
        'solution': function,
        'test_code': test_code
      }
      
      docker_write_status: bool = self.write_file_to_container(file_content=file_content, container_dir="test")
      if docker_write_status == False:
        print(f"Error during get_metrics:")
      #xecute code string & timeit
      runtime, cpu_usage, mem_usage = 0.0, 0.0, 0.0
      for i in range(100):
        res = self.docker_container.exec_run("cd test && python test_code.py")
        #returns docker 'event'
        print("get_metriics: Running code execution…")
        output = res.output.decode('utf-8')
        metric_str = output.split(",")
        print("   get_metrics: (time taken)",output)
        print("   get_metrics: (output type)", type(output))
        
        highest_cpu, highest_mem, highest_runtime = float(metric_str[0]), float(metric_str[1]), float(metric_str[2])
        runtime += highest_runtime
        cpu_usage += highest_cpu
        mem_usage += highest_mem
      runtime /= 100
      cpu_usage /= 100
      mem_usage /= 100
       
    except docker.errors.APIError as e:
      print(f"A Docker error occured: {e}")
    except Exception as e:
      print(f"Error: {e}")
    
    return {"runtime": runtime, "cpu": cpu_usage, "memory": mem_usage}
  
  def memory_or_runtime_better(self, runtime_delta, memory_delta) -> str:
    return "runtime"

  def compare_metrics(self, metrics_one: dict, metrics_two: dict) -> int:
    #returns:
      # 0 if metrics_one better than metrics_two
      # 1 if metrics_one worse than metrics_two
    
    runtime_epsilon = 5
    memory_epsilon = 5
    if metrics_one["runtime"] < metrics_two["runtime"]:
      runtime_epsilon = metrics_one["runtime"] * 0.01
    else:
      runtime_epsilon = metrics_two["runtime"] * 0.01
    
    if metrics_one["memory"] < metrics_two["memory"]:
      memory_epsilon = metrics_one["memory"] * 0.01
    else:
      memory_epsilon = metrics_two["memory"] * 0.01
      
    memory_runtime_epsilon = 10 #acceptible runtime deficit when memory is better
    runtime_memory_psilon = 10 #acceptible memory deficit when runtime is better
    runtime_delta = metrics_one["runtime"] - metrics_two["runtime"]
    memory_delta = metrics_one["memory"] - metrics_two["memory"]
    
    if abs(memory_delta) <= memory_epsilon and abs(runtime_delta) <= runtime_epsilon:
      #check absolute difference: prioritise runtime
      if runtime_delta < 0:
        return 0
      elif runtime_delta > 0:
        return 1
      elif runtime_delta == 0:
        if memory_delta == 0:
          return 0
        else:
          return 0  
    elif abs(runtime_delta) <= runtime_epsilon:
      if abs(memory_delta) > memory_epsilon:
        if memory_delta < 0: return 0
        else: return 1
    elif abs(memory_delta) <= memory_epsilon:
      if abs(runtime_delta) > runtime_epsilon:
        if runtime_delta < 0: return 0
        else: return 1
    elif abs(memory_delta) > memory_epsilon or abs(runtime_delta) > runtime_epsilon:
      if memory_delta < 0 and runtime_delta > 0:
        #metrics_one has better memory but worse runtime
        result = self.memory_or_runtime_better(runtime_delta, memory_delta)
        if result == "memory":
          return 0
        else: return 1
      elif memory_delta > 0 and runtime_delta < 0:
        #metrics_one has better runtime but worse memory
        result = self.memory_or_runtime_better(runtime_delta, memory_delta)
        if result == "memory":
          return 1
        else: return 0
    return 0
  
  def iterate(self, num_iterations: int, function: str, test_cases: Optional[List[str]] = None):
    current_function = function
    if test_cases is None:
      #generate test-data
      test_cases = self.optimizer_agent.generate_test_cases(code=function)
    else:
      test_cases = self.validate_test_cases(test_cases)
    
    current_metrics = self.get_metrics(function, test_cases)
    for i in range(num_iterations):
      functions = self.optimizer_agent.optimize_code(current_function)
      print(f"""
Optimied functions: 
{functions}
            """)
      func_one, func_two, func_three = functions.solution_one, functions.solution_two, functions.solution_three
      metrics_one, metrics_two, metrics_three = self.get_metrics(func_one, test_cases), self.get_metrics(func_two, test_cases), self.get_metrics(func_three, test_cases)
      
      res_one = self.compare_metrics(metrics_one, metrics_two)
      champ = func_one
      champ_metrics = metrics_one
      if res_one == 1:
        #func_one worse than func_two
        champ, champ_metrics = func_two, metrics_two
      res_one = self.compare_metrics(champ_metrics, metrics_three)
      if res_one == 1:
        champ, champ_metrics = func_three, metrics_three
      res_one = self.compare_metrics(champ_metrics, current_function)
      if res_one == 1:
        champ, champ_metrics = current_function, current_metrics
        return current_function #function could not be improved
      current_function, current_metrics = champ, champ_metrics
      
    return current_function, current_metrics
    
      
      