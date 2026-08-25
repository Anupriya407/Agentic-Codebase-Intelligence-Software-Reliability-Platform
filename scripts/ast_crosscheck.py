import ast
from pathlib import Path

source = Path("tests/fixtures/python/tree_sitter_demo.py").read_text()

tree = ast.parse(source)

print("AST functions/classes:")

for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        print("FUNCTION:", node.name)

    elif isinstance(node, ast.ClassDef):
        print("CLASS:", node.name)