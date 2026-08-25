from pathlib import Path

import networkx as nx

from backend.parser import analyze_repository


def build_python_file_index(results: dict) -> dict:
    """
    Build a mapping from Python module names to repository-relative paths.
    """
    module_index = {}

    for file_path in results:
        path = Path(file_path)

        if path.suffix != ".py":
            continue

        parts = list(path.with_suffix("").parts)

        if parts[-1] == "__init__":
            module_name = ".".join(parts[:-1])
        else:
            module_name = ".".join(parts)

        module_index[module_name] = file_path

    return module_index


def resolve_import(
    import_statement: str,
    current_file: str,
    module_index: dict,
):
    """
    Resolve a Python import statement to a repository file.

    Returns:
        Repository-relative target path, or None if unresolved.
    """
    statement = import_statement.strip()

    if statement.startswith("import "):
        modules = statement[len("import "):].split(",")

        for module in modules:
            module = module.strip().split(" as ")[0]

            if module in module_index:
                return module_index[module]

            parts = module.split(".")

            for end in range(len(parts), 0, -1):
                candidate = ".".join(parts[:end])

                if candidate in module_index:
                    return module_index[candidate]

    elif statement.startswith("from "):
        remainder = statement[len("from "):]

        module_part = remainder.split(" import ", 1)[0].strip()

        # ---------------------------------------------------------
        # Relative import
        # ---------------------------------------------------------

        if module_part.startswith("."):
            dot_count = len(module_part) - len(
                module_part.lstrip(".")
            )

            relative_module = module_part[dot_count:]

            current_path = Path(current_file)

            current_parts = list(
                current_path.with_suffix("").parts
            )

            # The current file's directory represents its package.
            package_parts = current_parts[:-1]

            # One dot = current package.
            # Two dots = parent package, etc.
            levels_up = dot_count - 1

            if levels_up > len(package_parts):
                return None

            if levels_up:
                package_parts = package_parts[:-levels_up]

            if relative_module:
                target_parts = (
                    package_parts
                    + relative_module.split(".")
                )
            else:
                target_parts = package_parts

            candidate_module = ".".join(target_parts)

            if candidate_module in module_index:
                return module_index[candidate_module]

            # Try the module as a normal Python package.
            if candidate_module + ".__init__" in module_index:
                return module_index[
                    candidate_module + ".__init__"
                ]

            return None

        # ---------------------------------------------------------
        # Absolute import
        # ---------------------------------------------------------

        if module_part in module_index:
            return module_index[module_part]

        parts = module_part.split(".")

        for end in range(len(parts), 0, -1):
            candidate = ".".join(parts[:end])

            if candidate in module_index:
                return module_index[candidate]

    return None


def build_function_index(graph: nx.DiGraph) -> dict:
    """
    Build indexes for resolving function call names.

    Returns:
        {
            "by_name": {
                function_name: [function_node, ...]
            },
            "by_file_and_name": {
                (file_path, function_name): [function_node, ...]
            },
            "by_class_and_name": {
                (class_name, function_name): [function_node, ...]
            },
        }
    """
    index = {
        "by_name": {},
        "by_file_and_name": {},
        "by_class_and_name": {},
    }

    for node, data in graph.nodes(data=True):
        if data.get("type") != "Function":
            continue

        name = data["name"]
        path = data["path"]
        containing_class = data["containing_class"]

        index["by_name"].setdefault(
            name,
            [],
        ).append(node)

        index["by_file_and_name"].setdefault(
            (path, name),
            [],
        ).append(node)

        if containing_class:
            index["by_class_and_name"].setdefault(
                (containing_class, name),
                [],
            ).append(node)

    return index


def resolve_call(
    call_expression: str,
    caller_path: str,
    caller_class: str | None,
    function_index: dict,
):
    """
    Resolve a call expression to the most likely Function node.

    Resolution priority:
        1. Same class + same function name.
        2. Same file + same function name.
        3. Globally unique function name.

    Returns:
        (target_node, status)

    status:
        "resolved"
        "ambiguous"
        "unresolved"
    """
    call = call_expression.strip()

    if not call:
        return None, "unresolved"

    # ---------------------------------------------------------
    # Extract the called name
    # ---------------------------------------------------------

    if "." in call:
        call_name = call.split(".")[-1]
    else:
        call_name = call

    # Remove possible call syntax.
    call_name = call_name.split("(")[0].strip()

    if not call_name:
        return None, "unresolved"

    # ---------------------------------------------------------
    # 1. Same class
    # ---------------------------------------------------------

    if caller_class:
        candidates = function_index[
            "by_class_and_name"
        ].get(
            (caller_class, call_name),
            [],
        )

        if len(candidates) == 1:
            return candidates[0], "resolved"

        if len(candidates) > 1:
            return None, "ambiguous"

    # ---------------------------------------------------------
    # 2. Same file
    # ---------------------------------------------------------

    candidates = function_index[
        "by_file_and_name"
    ].get(
        (caller_path, call_name),
        [],
    )

    if len(candidates) == 1:
        return candidates[0], "resolved"

    if len(candidates) > 1:
        return None, "ambiguous"

    # ---------------------------------------------------------
    # 3. Globally unique name
    # ---------------------------------------------------------

    candidates = function_index[
        "by_name"
    ].get(
        call_name,
        [],
    )

    if len(candidates) == 1:
        return candidates[0], "resolved"

    if len(candidates) > 1:
        return None, "ambiguous"

    return None, "unresolved"


def build_graph(repo_path: str) -> nx.DiGraph:
    """
    Build the code knowledge graph.

    Nodes:
        File
        Class
        Function

    Edges:
        CONTAINS
        IMPORTS
        CALLS
    """
    graph = nx.DiGraph()

    repo_path = str(Path(repo_path).resolve())

    results = analyze_repository(repo_path)

    module_index = build_python_file_index(results)

    # =========================================================
    # 1. Create nodes and structural/import relationships
    # =========================================================

    for file_path, structure in results.items():
        file_node = f"file:{file_path}"

        graph.add_node(
            file_node,
            type="File",
            path=file_path,
        )

        class_nodes = {}

        # -----------------------------------------------------
        # Classes
        # -----------------------------------------------------

        for class_info in structure["classes"]:
            class_name = class_info["name"]

            class_node = (
                f"class:{file_path}:{class_name}:"
                f"{class_info['start_line']}"
            )

            graph.add_node(
                class_node,
                type="Class",
                name=class_name,
                path=file_path,
                start_line=class_info["start_line"],
                end_line=class_info["end_line"],
            )

            graph.add_edge(
                file_node,
                class_node,
                type="CONTAINS",
            )

            class_nodes[class_name] = class_node

        # -----------------------------------------------------
        # Functions / Methods
        # -----------------------------------------------------

        for function_info in structure["functions"]:
            function_name = function_info["name"]

            function_node = (
                f"function:{file_path}:{function_name}:"
                f"{function_info['start_line']}"
            )

            graph.add_node(
                function_node,
                type="Function",
                name=function_name,
                path=file_path,
                containing_class=function_info["containing_class"],
                start_line=function_info["start_line"],
                end_line=function_info["end_line"],
                parameters=function_info["parameters"],
            )

            containing_class = function_info["containing_class"]

            if (
                containing_class
                and containing_class in class_nodes
            ):
                parent_node = class_nodes[containing_class]
            else:
                parent_node = file_node

            graph.add_edge(
                parent_node,
                function_node,
                type="CONTAINS",
            )

        # -----------------------------------------------------
        # Imports
        # -----------------------------------------------------

        for import_statement in structure["imports"]:
            target_path = resolve_import(
                import_statement,
                file_path,
                module_index,
            )

            if target_path is None:
                continue

            target_node = f"file:{target_path}"

            graph.add_edge(
                file_node,
                target_node,
                type="IMPORTS",
                import_statement=import_statement,
            )

    # =========================================================
    # 2. Build function index
    # =========================================================

    function_index = build_function_index(graph)

    # =========================================================
    # 3. Resolve CALLS relationships
    # =========================================================

    for file_path, structure in results.items():
        for function_info in structure["functions"]:

            caller_node = (
                f"function:{file_path}:"
                f"{function_info['name']}:"
                f"{function_info['start_line']}"
            )

            for call_expression in function_info["calls"]:

                target_node, status = resolve_call(
                    call_expression,
                    file_path,
                    function_info["containing_class"],
                    function_index,
                )

                # Only confident resolutions become graph edges.
                if status != "resolved":
                    continue

                graph.add_edge(
                    caller_node,
                    target_node,
                    type="CALLS",
                    call_expression=call_expression,
                )

    return graph


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print(
            "Usage: "
            "uv run python -m backend.graph_builder "
            "<repository-path>"
        )
        raise SystemExit(1)

    repo_path = sys.argv[1]

    graph = build_graph(repo_path)

    print("Graph built successfully.")
    print("Nodes:", graph.number_of_nodes())
    print("Edges:", graph.number_of_edges())

    file_nodes = [
        node
        for node, data in graph.nodes(data=True)
        if data["type"] == "File"
    ]

    class_nodes = [
        node
        for node, data in graph.nodes(data=True)
        if data["type"] == "Class"
    ]

    function_nodes = [
        node
        for node, data in graph.nodes(data=True)
        if data["type"] == "Function"
    ]

    contains_edges = [
        (source, target)
        for source, target, data in graph.edges(data=True)
        if data["type"] == "CONTAINS"
    ]

    import_edges = [
        (source, target)
        for source, target, data in graph.edges(data=True)
        if data["type"] == "IMPORTS"
    ]

    call_edges = [
        (source, target)
        for source, target, data in graph.edges(data=True)
        if data["type"] == "CALLS"
    ]

    print("File nodes:", len(file_nodes))
    print("Class nodes:", len(class_nodes))
    print("Function nodes:", len(function_nodes))
    print("CONTAINS edges:", len(contains_edges))
    print("IMPORTS edges:", len(import_edges))
    print("CALLS edges:", len(call_edges))