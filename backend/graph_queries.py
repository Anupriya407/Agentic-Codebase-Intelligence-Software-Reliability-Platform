from backend.graph_builder import build_graph


def find_function_node(graph, path, name):
    matches = [
        node
        for node, data in graph.nodes(data=True)
        if data.get("type") == "Function"
        and data.get("path") == path
        and data.get("name") == name
    ]

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one function, found {len(matches)}"
        )

    return matches[0]


def callers_of(graph, function_node):
    return [
        {
            "path": graph.nodes[node]["path"],
            "name": graph.nodes[node]["name"],
            "start_line": graph.nodes[node]["start_line"],
        }
        for node in graph.predecessors(function_node)
        if graph.edges[node, function_node].get("type") == "CALLS"
    ]


def calls_of(graph, function_node):
    return [
        {
            "path": graph.nodes[node]["path"],
            "name": graph.nodes[node]["name"],
            "start_line": graph.nodes[node]["start_line"],
        }
        for node in graph.successors(function_node)
        if graph.edges[function_node, node].get("type") == "CALLS"
    ]


def files_importing(graph, file_node):
    return [
        graph.nodes[node]["path"]
        for node in graph.predecessors(file_node)
        if graph.edges[node, file_node].get("type") == "IMPORTS"
    ]


if __name__ == "__main__":
    graph = build_graph("data/repositories/requests")

    target_function = find_function_node(
        graph,
        "src\\requests\\sessions.py",
        "request",
    )

    print("\nWHO CALLS request()?")

    for caller in callers_of(graph, target_function):
        print(caller)

    print("\nWHAT DOES request() CALL?")

    for callee in calls_of(graph, target_function):
        print(callee)

    target_file = "file:src\\requests\\sessions.py"

    print("\nWHAT FILES IMPORT sessions.py?")

    for importer in files_importing(graph, target_file):
        print(importer)