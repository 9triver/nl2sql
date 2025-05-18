import json
from textwrap import dedent
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from agno.tools import Toolkit
from graphviz import Digraph
from haystack.components.embedders import OpenAITextEmbedder
from haystack.utils import Secret
from neo4j import GraphDatabase, Record, ResultSummary, basic_auth
from neo4j.exceptions import ClientError, CypherSyntaxError
from neo4j.graph import Node, Path, Relationship
from neo4j.time import DateTime
from neo4j_haystack.client import Neo4jClient, Neo4jClientConfig
from neo4j_haystack.client.neo4j_client import DEFAULT_NEO4J_DATABASE


class Neo4jTools(Toolkit):
    name = "neo4j_tools"

    def __init__(
        self,
        name: str = name,
        tools: List[Callable] = [],
        instructions: Optional[str] = None,
        add_instructions: bool = False,
        include_tools: Optional[list[str]] = None,
        exclude_tools: Optional[list[str]] = None,
        cache_results: bool = False,
        cache_ttl: int = 3600,
        cache_dir: Optional[str] = None,
        auto_register: bool = False,
        user: str = "",
        password: str = "",
        database: str = DEFAULT_NEO4J_DATABASE,
        embed_model_name: str = "m3e-base",
        embed_base_url: str = "http://localhost:9997/v1",
        embed_api_key: str = "not_empty",
        db_uri: Optional[str] = None,
        dialect: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        schema: bool = False,
        labels: bool = False,
        relationships: bool = False,
        similar_nodes: bool = False,
        execution: bool = False,
    ):
        super().__init__(
            name=name,
            tools=tools,
            instructions=instructions,
            add_instructions=add_instructions,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
            cache_results=cache_results,
            cache_ttl=cache_ttl,
            cache_dir=cache_dir,
            auto_register=auto_register,
        )
        self.user = user
        self.password = password
        self.database = database
        db_uri = db_uri or f"{dialect}://{host}:{port}"
        self.db_uri = db_uri
        self.dialect = dialect
        self.host = host
        self.port = port

        self._driver = GraphDatabase.driver(uri=db_uri, auth=basic_auth(user, password))
        self._driver.verify_connectivity()

        self.text_embedder = OpenAITextEmbedder(
            model=embed_model_name,
            api_base_url=embed_base_url,
            api_key=Secret.from_token(embed_api_key),
        )

        if schema:
            self.register(self.show_schema)
        if labels:
            self.register(self.show_labels)
        if relationships:
            self.register(self.show_relationships)
        if similar_nodes:
            self.register(self.get_similar_node)
        if execution:
            self.register(self.execute_cypher)

    def show_schema(self) -> str:
        """显示Neo4j数据库的模式。"""
        return self.execute_cypher(cypher="CALL db.schema.visualization()")

    def show_labels(self) -> str:
        """显示Neo4j数据库中的所有标签。"""
        labels, _, _ = self._execute_cypher("""CALL db.labels() """)
        labels = [label["label"] for label in labels]
        return f"Node labels:{labels}"

    def show_relationships(self) -> str:
        """显示Neo4j数据库中的所有关系。"""
        relationships, _, _ = self._execute_cypher(cypher="CALL db.relationshipTypes()")
        relationships = [
            relationship["relationshipType"] for relationship in relationships
        ]
        return f"Relationship:{relationships}"

    def get_similar_node(self, query: str) -> str:
        """使用该函数查找与给定查询相似的节点。

        参数:
            query (str): 用于查找相似节点的查询字符串

        返回:
            str: JSON格式字符串，包含按相关性排序的最相似节点
        """
        top_k = 1
        # get all index names
        result, _, _ = self._execute_cypher(cypher="SHOW INDEXES")
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

    def execute_cypher(self, cypher: str) -> str:
        """执行Cypher语句并返回结果。

        参数:
            cypher (str): 要执行的Cypher查询语句

        返回:
            str:
                - 如果结果包含图形关系，返回DOT格式的图数据
                - 如果结果是普通记录，返回JSON格式字符串
                - 如果存在语法错误，返回错误信息
        """
        try:
            formatted_records, digraph, formatted_summary = self._execute_cypher(
                cypher=cypher
            )
        except CypherSyntaxError as e:
            return e.message

        result_str = (
            json.dumps(obj=formatted_records, ensure_ascii=False, indent=2)
            if len(digraph.body) < 1
            else digraph.source
        )
        result_str = result_str.replace('\\"', "'").replace("\\'", "'")

        return_str = ""
        if len(formatted_summary) > 0:
            return_str += f"Summary:\n{formatted_summary}\n\n"
        if len(result_str) > 0 and result_str != "[]":
            return_str += f"Result:\n{result_str}"
        return return_str

    def _execute_cypher(
        self, cypher: str, parameters=None
    ) -> Tuple[List[Dict[str, Any]], Digraph, str]:
        """执行Cypher查询语句并返回格式化结果和图形表示。

        参数:
            cypher (str): 要执行的Cypher查询语句
            parameters (dict, optional): 可选的查询参数，默认为None

        返回:
            Tuple[List[Dict[str, Any]], Digraph]:
                - 字典组成的列表，表示格式化后的查询结果
                - 表示查询结果关系的Digraph对象
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

    def _format_records(
        self, keys: list[str], records: list[Record]
    ) -> Tuple[List[Dict[str, Any]], Digraph]:
        """将原始数据库记录格式化为结构化字典和图表示。

        Args:
            keys: Cypher查询结果中的键（字段名）
            records: 数据库返回的原始记录

        Returns:
            Tuple[List[Dict[str, Any]], Digraph]:
                - 格式化的记录字典列表
                - 表示节点关系的Digraph图对象
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
        """将记录（或嵌套数据结构）格式化为JSON兼容格式，并更新提供的图表可视化

        参数:
            data: 需要格式化的输入数据，支持多种类型（基本类型、字典、列表、Node、Relationship等）
            digraph (Digraph): 用于可视化关系的有向图对象（默认：名为"Result"的空图）
            entity_set (Set): 用于跟踪已处理实体（节点/关系）的集合，避免重复处理（默认：空集合）

        返回:
            包含以下元素的元组:
                - formatted_data: 格式化后的JSON兼容数据（字典或列表）
                - digraph: 更新后的关系图对象
                - entity_set: 更新后的已处理实体集合

        异常:
            TypeError: 当输入数据类型不被支持时抛出

        注意:
            - 支持处理基本类型（int/str/float）、DateTime、字典、列表、Path、Node和Relationship
            - 对于Node/Relationship对象，会将其添加为图中的节点/边，并通过`entity_set`确保唯一性
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
                # filter enpty value
                if formatted_value is None:
                    continue
                try:
                    if len(formatted_value) <= 0:
                        continue
                except TypeError:
                    pass
                formatted_data[key] = formatted_value
            return formatted_data, digraph, entity_set
        elif isinstance(data, (list, tuple)):
            filtered = []
            for item in data:
                processed_item, digraph, entity_set = self._format_record_json(
                    data=item, digraph=digraph, entity_set=entity_set
                )
                if not isinstance(
                    processed_item, float
                ):  # filter list[float](possible embedding)
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
            formatted_data = {}
            if data.type is not None and len(data.type) > 0:
                formatted_data["type"] = data.type
            if data._properties is not None and len(data._properties.keys()) > 0:
                formatted_data["properties"] = json.dumps(
                    obj=data._properties, ensure_ascii=False
                )
            if data not in entity_set:
                entity_set.add(data)
                digraph.edge(
                    tail_name=formatted_start_node["name"],
                    head_name=formatted_end_node["name"],
                    label=None,
                    _attributes=None,
                    **formatted_data,
                )
            return formatted_data, digraph, entity_set
        else:
            raise TypeError(f"Unknow Type {type(data)}")

    def _remove_keys(self, obj, keys_to_remove):
        """递归地从嵌套字典或列表中移除指定的键

        参数:
            obj (dict | list): 要处理的输入对象（字典或列表）
            keys_to_remove (set | list): 需要从对象中移除的键集合

        返回:
            dict | list: 递归移除指定键后的新对象
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
        """递归地从嵌套字典或列表中提取并仅保留指定的键

        参数:
            obj (dict | list): 要处理的输入对象（字典或列表）
            keys_to_keep (set | list): 需要保留的键集合

        返回:
            dict | list: 递归处理后仅包含指定键的新对象
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
