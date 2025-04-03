import unittest
from function import factorial

import psutil, time, threading
import unittest

def monitor(interval, stop_event):
  #no GPU monitoring yet
  start_time = time.time()
  while not stop_event.is_set():
    cpu = psutil.cpu_percent(interval=interval)
    mem = psutil.virtual_memory().percent
    
    time.sleep(0.00005) #to avoid overlapping measurements
  endtime = time.time()
  runtime = endtime - start_time
  print(f"cpu: {cpu}, mem: {mem}, runtime: {runtime}")
  return [cpu, mem, runtime]
  
stop_event = threading.Event()
monitor_thread = threading.Thread(target=monitor, args=(0.000005, stop_event))

class TestFactorial(unittest.TestCase):

    def test_factorial_zero(self):
        self.assertEqual(factorial(0), 1)

    def test_factorial_one(self):
        self.assertEqual(factorial(1), 1)

    def test_factorial_positive(self):
        self.assertEqual(factorial(5), 120)

    def test_factorial_ten(self):
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_edge(self):
        self.assertEqual(factorial(3), 6)
        
if __name__ == '__main__':
    monitor_thread.start()
    unittest.main()
    stop_event.set()
    monitor_thread.join()