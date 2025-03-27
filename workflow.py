import docker.errors
from code_optimiser import CodeOptimizer
from typing import Optional, List
import docker
import json
import time


#CodeOptimizer(old_code): new_code --> Run code --> get_metrics()
# if new_metrics better than old_metrics, 
#   old_code = new_code, old_metrics = new_metrics
#   Code_optimizer(new_code) (repeat)
# else if new_metrics ≈ old_metrics:
#     if num_iterations < 3:
#         old_code = new_code
#         CodeOptimizer(old_code)
#     else:
#         stop
# else if new_metrics worse_than old_metrics
#     stop? function is already optimizer //this will probably not happen


class Workflow:
  def __init__(self):
    self.optimizer_agent = CodeOptimizer()
    print("Initializing Docker…")
    #docker settings
    # self.docker_init = docker.DockerClient(base_url="unix://var/run/docker.sock")
    self.docker_client = docker.from_env()
    self.container_name = 'python-code-executor'
    try:
      container_list = self.docker_client.containers.list(filters={"name":self.container_name})
      if container_list:
        self.docker_container = container_list[0]
      else:
        self.docker_container = self.docker_client.containers.run(
          'python:3.9-slim', 
          detach=True,
          name=self.container_name,
          tty=True 
          )
    except docker.errors.APIError as e:
      print(f"Error while initializing docker for code execution: {e}")
    self.docker_container.exec_run(['mkdir', 'test'])
    print("Docker setup completed.")
    #test to ensure docker-api is working
    # print(self.docker_client.containers.run("alpine", ["echo", "hello", "world"]))
  def get_metrics(self, function: str, test_cases: Optional[List[str]] = None): #test-cases or test-data required to actually time the function    
    if test_cases is None:
      #generate test-data
      test_cases = self.optimizer_agent.generate_test_cases(code=function)

    #run every test-case in docker-container
    try:
      with open('./test/function.py', 'w') as f:
        code_string = f""" 
        import unittest
        {function}
        
        {test_cases}
        """
        f.write(code_string)

      #xecute code string & timeit
      runtime, cpu_usage, mem_usage = 0.0, 0.0, 0.0
      with open("./test/function.py", 'rb') as f:
       self.docker_container.put_archive("./test/", f.read())
       for i in range(100):
        res = self.docker_container.exec_run(["time", "python", "app/function.py"], stream=True)
        output = res.output.decode('utf-8')
        
        stats_stream = self.docker_container.stats(stream=True)
        highest_cpu, highest_mem = -1.0, -2.0
        for stat_json in stats_stream:
          stat = json.loads(stat_json)
          
          cpu_usage_current = stat["cpu_stats"]["cpu_usage"]["total_usage"]
          mem_usage_current = stat["memory_stats"]["usage"]
          
          if cpu_usage_current > highest_cpu:
            highest_cpu = cpu_usage_current
          
          if mem_usage_current > highest_mem:
            highest_mem = mem_usage_current
          
          time.sleep(0.5)
          try:
            output.next()
          except StopIteration as e:
            break
        
        cpu_usage += highest_cpu
        mem_usage += highest_mem
        
        if i == 1:
          output_dict = json.loads(output)
          print(output_dict)
          
        output_arr = output.split(" ")
        runtime += float(output_arr[-2]) #we just get the total runtime of the script
       runtime, cpu_usage, mem_usage = runtime/100, cpu_usage/100, mem_usage/100
       
    except docker.errors.APIError as e:
      print(f"A Docker error occured: {e}")
    except Exception as e:
      print(f"Error: {e}")
    
    return {"runtime": runtime, "cpu": cpu_usage, "memory": mem_usage}
  
  def memory_or_runtime_better(self, runtime_delta, memory_delta) -> str:
    return "runtime"

  def compare_metrics(self, metrics_one: str, metrics_two: str) -> int:
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
  
  def iterate(self, num_iterations: int, function: str):
    current_function = function
    current_metrics = self.get_metrics(function)
    
    for i in range(num_iterations):
      functions = self.optimizer_agent.optimize_code(current_function)
      func_one, func_two, func_three = functions["solution_one"], functions["solution_two"], functions["solution_three"]
      metrics_one, metrics_two, metrics_three = self.get_metrics(func_one), self.get_metrics(func_two), self.get_metrics(func_three)
      
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
    
      
      