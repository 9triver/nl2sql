import json
from typing import Optional, Tuple, Set, List, Dict, Any, Callable
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
            self.register(self.execute_cypher)

    def show_indexes(self) -> str:
        """使用此函数显示Neo4j数据库中的索引。

        返回:
            str: 包含索引信息的JSON格式字符串，出于简洁性考虑移除了部分键值。
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
        return json.dumps(obj=result, ensure_ascii=False, indent=2)

    def show_labels(self) -> str:
        """使用此函数显示Neo4j数据库中所有标签的信息。

        返回:
            str: 以JSON格式返回节点标签及其数量信息。
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
        """使用此函数显示Neo4j数据库中所有关系的信息。

        返回:
            str: 以表格形式展示的关系类型及其数量的字符串。
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
        """使用该函数查找与给定查询相似的节点。

        参数:
            query (str): 用于查找相似节点的查询字符串

        返回:
            str: JSON格式字符串，包含按相关性排序的最相似节点
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
        """使用该函数验证Cypher语句的语法是否正确。

        Args:
            cypher (str): 待验证的Cypher语句字符串

        Returns:
            str: 若存在语法错误则返回错误信息，否则返回 "No Cypher Syntax Error"
        """
        try:
            _, _, summary = self._execute_cypher_statement(
                cypher=cypher, parameters=None
            )
        except CypherSyntaxError as e:
            return e.message
        return f"No Cypher Syntax Error, Summary:{summary}"

    def execute_cypher(self, cypher: str) -> str:
        """执行Cypher语句并返回结果。

        参数:
            cypher (str): 要执行的Cypher查询语句

        返回:
            str:
                - 如果结果包含图形关系，返回图数据源（如DOT格式）
                - 如果结果是普通记录，返回JSON格式字符串
                - 如果存在语法错误，返回错误信息
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

    def _format_records(self, keys, records) -> Tuple[List[Dict[str, Any]], Digraph]:
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
                    attrs=json.dumps(obj=formatted_data, ensure_ascii=False, indent=2),
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
