import ast


class Tree(ast.NodeVisitor):
  def __init__(self):
    self.nodes = []

  def visit(self, node):
    self.nodes.append(node)
    self.generic_visit(node)
    return self.nodes


class CodeParser:
  def extract_code(self, filepath):
    try:
      with open(filepath, "r", encoding="utf-8") as file:
        return file.read()
    except FileNotFoundError:
      print(f"Error: File not found at {filepath}")
      return None
    except IOError as e:
      print(f"Error: An I/O error occurred: {e}")
      return None
    except UnicodeDecodeError:
      print("Error: Could not decode the file using utf-8 encoding. Try a different encoding.")
      return None

  def parse(self, code):
    try:
      tree = ast.parse(code)
      return tree
    except SyntaxError as e:
      print(f"Syntax Error: {e}")

  def visit_code_tree(self, code):
    tree = self.parse(code)
    tree_extractor = Tree()
    return tree_extractor.visit(tree)

  def get_code_tree(self, filepath):
    code = self.extract_code(filepath)
    return self.visit_code_tree(code)

  def print_code_tree(self, filepath):
    code_tree = self.get_code_tree(filepath)
    if code_tree:
      for node in code_tree:
        print(ast.dump(node))
