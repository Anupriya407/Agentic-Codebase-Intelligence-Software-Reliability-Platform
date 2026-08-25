import os

import networkx as nx

from neo4j import GraphDatabase


class Neo4jStore:
    """
    Persist the NetworkX code knowledge graph in Neo4j.
    """

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
    ):
        self.driver = GraphDatabase.driver(
            uri,
            auth=(username, password),
        )

    def verify_connection(self):
        """
        Verify that Neo4j is reachable and credentials are valid.
        """
        self.driver.verify_connectivity()

    def close(self):
        """
        Close the Neo4j driver.
        """
        self.driver.close()

    def clear_database(self):
        """
        Delete the existing graph data.

        This is intentionally limited to graph nodes and
        relationships created by this project.
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (n)
                DETACH DELETE n
                """
            )

    def write_graph(self, graph: nx.DiGraph):
        """
        Write a NetworkX graph into Neo4j.
        """
        with self.driver.session() as session:
            for node, data in graph.nodes(data=True):
                session.execute_write(
                    self._create_node,
                    node,
                    data,
                )

            for source, target, data in graph.edges(data=True):
                session.execute_write(
                    self._create_relationship,
                    source,
                    target,
                    data,
                )

    @staticmethod
    def _create_node(
        tx,
        node_id,
        data,
    ):
        """
        Create one graph node.
        """
        node_type = data["type"]

        properties = {
            key: value
            for key, value in data.items()
            if key != "type"
        }

        properties["node_id"] = node_id

        query = f"""
        MERGE (n:{node_type} {{node_id: $node_id}})
        SET n += $properties
        """

        tx.run(
            query,
            node_id=node_id,
            properties=properties,
        )

    @staticmethod
    def _create_relationship(
        tx,
        source,
        target,
        data,
    ):
        """
        Create one graph relationship.
        """
        relationship_type = data["type"]

        properties = {
            key: value
            for key, value in data.items()
            if key != "type"
        }

        query = f"""
        MATCH (source {{node_id: $source}})
        MATCH (target {{node_id: $target}})
        MERGE (source)-[r:{relationship_type}]->(target)
        SET r += $properties
        """

        tx.run(
            query,
            source=source,
            target=target,
            properties=properties,
        )


def create_store():
    """
    Create a Neo4jStore using environment variables.

    Required:
        NEO4J_URI
        NEO4J_USERNAME
        NEO4J_PASSWORD
    """
    uri = os.getenv(
        "NEO4J_URI",
        "bolt://localhost:7687",
    )

    username = os.getenv(
        "NEO4J_USERNAME",
        "neo4j",
    )

    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise RuntimeError(
            "NEO4J_PASSWORD environment variable is not set."
        )

    return Neo4jStore(
        uri=uri,
        username=username,
        password=password,
    )