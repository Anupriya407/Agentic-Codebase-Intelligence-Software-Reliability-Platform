from dataclasses import asdict, dataclass, field
from pathlib import Path

import ast
import sys

from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_python as tree_sitter_python


PYTHON_LANGUAGE = Language(tree_sitter_python.language())


@dataclass
class ClassInfo:
    name: str
    start_line: int
    end_line: int


@dataclass
class FunctionInfo:
    name: str
    containing_class: str | None
    start_line: int
    end_line: int
    parameters: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


@dataclass
class FileStructure:
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


def get_parameters(parameters_node):
    parameters = []

    if parameters_node:
        for child in parameters_node.named_children:
            if child.type in {
                "identifier",
                "typed_parameter",
                "default_parameter",
            }:
                parameters.append(child.text.decode())

    return parameters


def find_calls(node, source):
    calls = []

    query = Query(
        PYTHON_LANGUAGE,
        """
        (call
            function: (_) @function
        )
        """,
    )

    cursor = QueryCursor(query)
    captures = cursor.captures(node)

    for function_node in captures.get("function", []):
        # Ignore calls that belong to a nested function.
        current = function_node.parent

        belongs_to_nested_function = False

        while current is not None and current != node:
            if current.type == "function_definition":
                belongs_to_nested_function = True
                break

            current = current.parent

        if belongs_to_nested_function:
            continue

        text = source[
            function_node.start_byte:function_node.end_byte
        ].decode("utf-8")

        calls.append(text)

    return calls


def find_python_files(repo_path: str):
    repo = Path(repo_path)

    return sorted(
        path
        for path in repo.rglob("*.py")
        if ".git" not in path.parts
        and "__pycache__" not in path.parts
        and ".venv" not in path.parts
    )


def parse_python_file(file_path: str) -> FileStructure:
    source = Path(file_path).read_bytes()

    parser = Parser(PYTHON_LANGUAGE)
    tree = parser.parse(source)

    result = FileStructure()

    def process_function(node, containing_class=None):
        name_node = node.child_by_field_name("name")
        parameters_node = node.child_by_field_name("parameters")

        calls = find_calls(node, source)

        result.functions.append(
            FunctionInfo(
                name=name_node.text.decode(),
                containing_class=containing_class,
                start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1,
                parameters=get_parameters(parameters_node),
                calls=calls,
            )
        )

        result.calls.extend(calls)

        body = node.child_by_field_name("body")

        if body:
            for child in body.named_children:
                if child.type == "function_definition":
                    process_function(child, containing_class)

    def process_class(node, parent_class=None):
        name_node = node.child_by_field_name("name")
        class_name = name_node.text.decode()

        result.classes.append(
            ClassInfo(
                name=class_name,
                start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1,
            )
        )

        body = node.child_by_field_name("body")

        if body:
            for child in body.named_children:

                if child.type == "function_definition":
                    process_function(child, class_name)

                elif child.type == "class_definition":
                    process_class(child, class_name)

    for node in tree.root_node.named_children:

        if node.type in {"import_statement", "import_from_statement"}:
            result.imports.append(node.text.decode())

        elif node.type == "class_definition":
            process_class(node)

        elif node.type == "function_definition":
            process_function(node)

    return result


def ast_cross_check(file_path: str):
    source = Path(file_path).read_text()

    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return {
            "error": f"Syntax error: {error}",
            "classes": [],
            "functions": [],
            "imports": [],
        }

    classes = []
    functions = []
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

        elif isinstance(node, ast.Import):
            imports.append(
                "import " + ", ".join(alias.name for alias in node.names)
            )

        elif isinstance(node, ast.ImportFrom):
            names = ", ".join(alias.name for alias in node.names)

            if node.module:
                imports.append(f"from {node.module} import {names}")
            else:
                imports.append(f"from . import {names}")

    return {
        "classes": classes,
        "functions": functions,
        "imports": imports,
    }


def analyze_repository(repo_path: str):
    python_files = find_python_files(repo_path)

    file_results = {}

    for file_path in python_files:
        structure = parse_python_file(file_path)

        relative_path = str(Path(file_path).relative_to(repo_path))

        file_results[relative_path] = asdict(structure)

    return file_results


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python backend/parser.py <repository-path>")
        raise SystemExit(1)

    repo_path = sys.argv[1]

    results = analyze_repository(repo_path)

    print(f"Parsed {len(results)} Python files.")

    for file_path, structure in list(results.items())[:3]:
        print(f"\nFILE: {file_path}")
        print(structure)