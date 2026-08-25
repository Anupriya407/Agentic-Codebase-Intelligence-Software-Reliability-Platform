from backend.graph_builder import build_graph
from backend.neo4j_store import create_store


def main():
    repo_path = "data/repositories/requests"

    print("Building NetworkX graph...")
    graph = build_graph(repo_path)

    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")

    store = create_store()

    try:
        print("Verifying Neo4j connection...")
        store.verify_connection()
        print("Neo4j connection: OK")

        print("Clearing existing Neo4j graph...")
        store.clear_database()

        print("Writing graph to Neo4j...")
        store.write_graph(graph)

        print("Graph written to Neo4j successfully.")

    finally:
        store.close()


if __name__ == "__main__":
    main()