import json
from typing import Optional, Tuple, Set, List, Dict, Any
from textwrap import dedent
from agno.tools import Toolkit
from neo4j import GraphDatabase, basic_auth
from neo4j.graph import Node, Relationship, Path
from neo4j.time import DateTime
from neo4j.exceptions import ClientError, CypherSyntaxError
from neo4j.work.summary import ResultSummary
from neo4j_haystack.client import Neo4jClient, Neo4jClientConfig
from haystack.components.embedders import SentenceTransformersTextEmbedder
from neo4j_haystack.client.neo4j_client import DEFAULT_NEO4J_DATABASE
from tabulate import tabulate, TableFormat, Line
from graphviz import Digraph

from loguru import logger


class Neo4jTools(Toolkit):
    custom_format = TableFormat(
        lineabove=Line("", "", "", ""),  # 无上边框
        linebelowheader=Line("-", "-", "-", ""),  # 标题下方有分割线
        linebetweenrows=None,  # 无行间分隔线
        linebelow=None,  # 无底部分隔线
        headerrow=("|", "|", "|"),  # 在表头的列之间使用 |
        datarow=("|", "|", "|"),  # 在数据行的列之间使用 |
        padding=1,  # 确保列内容与分割线之间有足够的间距
        with_header_hide=None,
    )
    name = "neo4j_tools"

    def __init__(
        self,
        user: str,
        password: str,
        name: str = name,
        instructions: Optional[str] = None,
        add_instructions: bool = False,
        cache_results: bool = False,
        cache_ttl: int = 3600,
        cache_dir: Optional[str] = None,
        database: str = DEFAULT_NEO4J_DATABASE,
        embedding_dim: int = 768,
        embedding_field: str = "embedding",
        embedding_model: str = "moka-ai/m3e-base",
        db_uri: Optional[str] = None,
        dialect: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        labels: bool = False,
        relationships: bool = False,
        similar_nodes: bool = False,
        syntax: bool = False,
        execution: bool = False,
    ):
        super().__init__(
            name=name,
            instructions=instructions,
            add_instructions=add_instructions,
            cache_results=cache_results,
            cache_ttl=cache_ttl,
            cache_dir=cache_dir,
        )
        self.user = user
        self.password = password
        self.database = database
        self.embedding_dim = embedding_dim
        self.embedding_field = embedding_field
        db_uri = db_uri or f"{dialect}://{host}:{port}"
        self.db_uri = db_uri
        self.dialect = dialect
        self.host = host
        self.port = port

        self._driver = GraphDatabase.driver(uri=db_uri, auth=basic_auth(user, password))
        self._driver.verify_connectivity()

        self.text_embedder = SentenceTransformersTextEmbedder(
            model=embedding_model, trust_remote_code=True
        )
        self.text_embedder.warm_up()

        if labels:
            self.register(self.show_labels)
        if relationships:
            self.register(self.show_relationships)
        if similar_nodes:
            self.register(self.get_similar_node)
        if syntax:
            self.register(self.check_cypher_syntax)
        if execution:
            self.register(self.execute_cypher_statement)

    def show_indexes(self) -> str:
        """Use this function to show the indexes in the Neo4j database.

        Returns:
            str: A JSON-formatted string containing the index information, with certain keys removed for clarity.
        """
        result, _, _ = self._execute_cypher_statement(cypher="SHOW INDEXES")
        # filter
        result = self._remove_keys(
            obj=result,
            keys_to_remove=[
                "id",
                "state",
                "indexProvider",
                "populationPercent",
                "lastRead",
                "readCount",
            ],
        )
        return json.dumps(obj=result, indent=2, ensure_ascii=False)

    def show_labels(self) -> str:
        """Use this function to show all labels' infomation in neo4j database.

        Returns:
            str: Node labels and their counts in JSON format.
        """
        labels_table, _, _ = self._execute_cypher_statement(
            dedent(
                """\
            MATCH (n)
            RETURN labels(n) AS label, count(*) AS count
            ORDER BY count DESC\
        """
            )
        )
        labels_table = json.dumps(obj=labels_table, ensure_ascii=False, indent=2)
        return f"Node labels:{labels_table}"

    def show_relationships(self) -> str:
        """Use this function to show all relationships' infomation in neo4j database.

        Returns:
            str: Relationship types and their counts in a tabulated format.
        """
        records, _, _ = self._execute_cypher_statement(
            cypher="CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"
        )
        records = self._extract_keys(obj=records, keys_to_keep=["relationshipType"])
        rel_types = [record["relationshipType"] for record in records]

        rel_counts = []
        for rel_type in rel_types:
            records, _, _ = self._execute_cypher_statement(
                cypher=dedent(
                    f"""\
                    MATCH ()-[r:`{rel_type}`]->()
                    RETURN COUNT(r) AS count
                """
                ),
            )
            records = self._extract_keys(obj=records, keys_to_keep=["count"])
            rel_count = records[0]["count"]
            rel_counts.append([rel_types, rel_count])
        rel_table = tabulate(
            rel_counts,
            headers=["relationshipType", "count"],
            tablefmt=self.custom_format,
            stralign="left",
        )

        return f"Relationship types:{rel_table}"

    def get_similar_node(self, query: str) -> str:
        """Use this function to find nodes similar to a given query.

        Args:
            query (str): The query string to find similar nodes for.

        Returns:
            str: A JSON-formatted string containing the most similar nodes, sorted by relevance.
        """
        top_k = 1
        # get all index names
        result, _, _ = self._execute_cypher_statement(cypher="SHOW INDEXES")
        result = self._extract_keys(
            obj=result,
            keys_to_keep=["name"],
        )
        index_names = [r["name"] for r in result]

        client_config = Neo4jClientConfig(
            url=self.db_uri,
            database=self.database,
            username=self.user,
            password=self.password,
        )
        neo4j_client = Neo4jClient(client_config)
        neo4j_client.verify_connectivity()

        query_embedding = self.text_embedder.run(text=query)["embedding"]

        records = []
        for index_name in index_names:
            try:
                records.extend(
                    neo4j_client.query_embeddings(
                        index=index_name,
                        top_k=top_k,
                        embedding=query_embedding,
                    )
                )
            except ClientError:
                continue
        sorted_records = sorted(records, key=lambda x: x["score"], reverse=True)[:top_k]
        formatted_records, _, _ = self._format_record_json(data=sorted_records)
        return json.dumps(obj=formatted_records, ensure_ascii=False, indent=2)

    def check_cypher_syntax(self, cypher: str) -> str:
        """Use this function to check the syntax of a cypher statement.

        Args:
            cypher (str): The cypher statement string to be validated.

        Returns:
            str: If the cypher statement contains a syntax error, returns the error message.
                 Otherwise, returns "No Cypher Syntax Error".
        """
        try:
            _, _, summary = self._execute_cypher_statement(
                cypher=cypher, parameters=None
            )
        except CypherSyntaxError as e:
            return e.message
        return f"No Cypher Syntax Error, Summary:{summary}"

    def execute_cypher_statement(self, cypher: str) -> str:
        """Use this function to execute a cypher statement and return the results.

        Args:
            cypher (str): The cypher statement to execute.

        Returns:
            str:
                - If the execute results contain a graph (relationships), returns the graph source (e.g., DOT format).
                - If the execute results are plain records, returns them as a JSON-formatted string.
                - If there's a syntax error, returns the error message.
        """
        try:
            formatted_records, digraph, formatted_summary = (
                self._execute_cypher_statement(cypher=cypher)
            )
        except CypherSyntaxError as e:
            return e.message
        result = (
            json.dumps(obj=formatted_records, ensure_ascii=False, indent=2)
            if len(digraph.body) < 1
            else digraph.source.replace('\\"', "'")
        )
        return f"Summary:\n{formatted_summary}\n\nResult:\n{result}"

    def _execute_cypher_statement(
        self, cypher: str, parameters=None
    ) -> Tuple[List[Dict[str, Any]], Digraph]:
        """Execute a cypher statement and return the formatted results as well as a graph representation.

        Args:
            cypher (str): The cypher statement to execute.
            parameters (dict, optional): Optional parameters for the cypher statement. Defaults to None.

        Returns:
            Tuple[List[Dict[str, Any]], Digraph]:
                - A list of dictionaries representing formatted execute cypher results.
                - A Digraph object representing the relationships in the results.
        """
        parameters = parameters or {}

        records, summary, keys = self._driver.execute_query(
            query_=cypher,
            parameters_=parameters,
            database_=self.database,
        )

        formatted_records, digraph = self._format_records(keys=keys, records=records)
        formatted_summary = self._format_summary(summary=summary)
        return formatted_records, digraph, formatted_summary

    def _format_summary(self, summary: ResultSummary):
        formatted_summary = ""
        for notification in summary.summary_notifications:
            formatted_summary += f"{notification.title}\n{notification.description}\n\n"
        return formatted_summary

    def _format_records(self, keys, records) -> Tuple[List[Dict[str, Any]], Digraph]:
        """Format raw database records into structured dictionaries and a graph representation.

        Args:
            keys: The keys (field names) from the cypher result.
            records: The raw records returned by the database.

        Returns:
            Tuple[List[Dict[str, Any]], Digraph]:
                - A list of dictionaries with formatted records.
                - A Digraph object representing relationships between nodes.
        """
        formatted_records = []
        for record in records:
            formatted = {}
            for key in keys:
                value = record[key]
                formatted[key] = value
            formatted_records.append(formatted)

        formatted_records, digraph, _ = self._format_record_json(data=formatted_records)
        return formatted_records, digraph

    def _format_record_json(
        self,
        data,
        digraph: Digraph = Digraph(name="Result"),
        entity_set: Set = set(),
    ) -> List[Dict[str, Any]]:
        """Formats a record (or nested data structure) into a JSON-compatible format and updates the provided graph visualization.

        Args:
            data: The input data to be formatted, which can be of various types (e.g., primitive, dict, list, Node, Relationship).
            digraph (Digraph): A directed graph object for visualizing relationships (default: empty Digraph named "Result").
            entity_set (Set): A set to track processed entities (nodes/relationships) to avoid duplication (default: empty set).

        Returns:
            Tuple containing:
                - formatted_data: The formatted JSON-compatible data (dict or list).
                - digraph: The updated directed graph with nodes/edges for visualization.
                - entity_set: The updated set of processed entities.

        Raises:
            TypeError: If the input data type is not supported.

        Notes:
            - Handles primitive types (int, str, float), DateTime, dictionaries, lists, Path, Node, and Relationship.
            - For Node/Relationship objects, adds them as nodes/edges to the graph and ensures uniqueness via `entity_set`.
        """
        if data is None or isinstance(data, (int, str, float)):
            return data, digraph, entity_set
        elif isinstance(data, DateTime):
            return str(data), digraph, entity_set
        elif isinstance(data, dict):
            formatted_data = {}
            for key, value in data.items():
                formatted_value, digraph, entity_set = self._format_record_json(
                    data=value, digraph=digraph, entity_set=entity_set
                )
                formatted_data[key] = formatted_value
            return formatted_data, digraph, entity_set
        elif isinstance(data, (list, tuple)):
            filtered = []
            for item in data:
                processed_item, digraph, entity_set = self._format_record_json(
                    data=item, digraph=digraph, entity_set=entity_set
                )
                if not isinstance(processed_item, float):
                    filtered.append(processed_item)
            return filtered, digraph, entity_set
        elif isinstance(data, Path):
            formatted_nodes, digraph, entity_set = self._format_record_json(
                data=data.nodes, digraph=digraph, entity_set=entity_set
            )
            formatted_relationships, digraph, entity_set = self._format_record_json(
                data=data.relationships, digraph=digraph, entity_set=entity_set
            )
            formatted_data = {
                "nodes": formatted_nodes,
                "relationships": formatted_relationships,
            }
            return formatted_data, digraph, entity_set
        elif isinstance(data, Node):
            formatted_data, digraph, entity_set = self._format_record_json(
                data={**data}, digraph=digraph, entity_set=entity_set
            )
            if data not in entity_set:
                entity_set.add(data)
                digraph.node(
                    name=formatted_data["name"],
                    label=None,
                    _attributes=None,
                    **{k: str(v) for k, v in formatted_data.items() if k != "name"},
                )
            return formatted_data, digraph, entity_set
        elif isinstance(data, Relationship):
            formatted_start_node, digraph, entity_set = self._format_record_json(
                data=data.start_node, digraph=digraph, entity_set=entity_set
            )
            formatted_end_node, digraph, entity_set = self._format_record_json(
                data=data.end_node, digraph=digraph, entity_set=entity_set
            )
            formatted_data = {
                "start_node": formatted_start_node,
                "element_id": data.element_id,
                "type": data.type,
                "properties": data._properties,
                "end_node": formatted_end_node,
            }
            if data not in entity_set:
                entity_set.add(data)
                digraph.edge(
                    tail_name=formatted_start_node["name"],
                    head_name=formatted_end_node["name"],
                    attrs=json.dumps(obj=formatted_data, ensure_ascii=False),
                )
            return formatted_data, digraph, entity_set
        else:
            raise TypeError(f"Unknow Type {type(data)}")

    def _remove_keys(self, obj, keys_to_remove):
        """Recursively remove specified keys from a nested dictionary or list.

        Args:
            obj (dict | list): The input object (dictionary or list) to process.
            keys_to_remove (set | list): Collection of keys to remove from the object.

        Returns:
            dict | list: A new object with the specified keys removed recursively.
        """
        if isinstance(obj, dict):
            return {
                key: self._remove_keys(value, keys_to_remove)
                for key, value in obj.items()
                if key not in keys_to_remove
            }
        elif isinstance(obj, list):
            return [self._remove_keys(item, keys_to_remove) for item in obj]
        else:
            return obj

    def _extract_keys(self, obj, keys_to_keep):
        """Recursively extract and retain only the specified keys from a nested dictionary or list.

        Args:
            obj (dict | list): The input object (dictionary or list) to process.
            keys_to_keep (set | list): Collection of keys to retain in the object.

        Returns:
            dict | list: A new object with only the specified keys retained recursively.
        """
        if isinstance(obj, dict):
            filtered = {}
            for key in obj:
                if key in keys_to_keep:
                    filtered[key] = self._extract_keys(obj[key], keys_to_keep)
            return filtered
        elif isinstance({}, list):
            return [self._extract_keys(item, keys_to_keep) for item in obj]
        else:
            return obj
