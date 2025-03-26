import ast

class Tree(ast.NodeVisitor):
  def __init__(self):
    self.nodes = []

  def visit(self, node):
    self.nodes.append(node) #store the node itself.
    self.generic_visit(node)
    return self.nodes
  
class CodeParser:
  
  def __init__(self):
    pass
  
  def extract_code(self,filepath):
    try:
      with open(filepath, 'r', encoding='utf-8') as file:
        return file.read()
    except FileNotFoundError:
      print(f"Error: File not found at {filepath}")
      return None
    except IOError as e:
        print(f"Error: An I/O error occurred: {e}")
        return None
    except UnicodeDecodeError:
        print(f"Error: Could not decode the file using utf-8 encoding. Try a different encoding.")
        return None
  
  def parse(self, code):
    try:
      tree = ast.parse(code)
      return tree
    except SyntaxError as e:
      print(f"Syntax Error: {e}")
  
  def visit_code_tree(self, code):
    tree = self.parse(code)
    treeExtractor = Tree()
    arr = treeExtractor.visit(tree)
    return arr
  
  def get_code_tree(self, filepath):
    code = self.extract_code(filepath)
    codeTree = self.visit_code_tree(code)
    return codeTree
  
  def print_code_tree(self, filepath):
    codeTree = self.get_code_tree(filepath)
    if codeTree:
      for node in codeTree:
        print(ast.dump(node))