import os
import sys

sys.path.insert(0, os.path.abspath("../src"))
from textwrap import dedent

from param import Parameter
from tools.neq4j import Neo4jTools


class TestNeo4jTools:
    param = Parameter(config_file_path="../config.yaml")
    neo4j_tools = Neo4jTools(
        user=param.DATABASE_USER,
        password=param.DATABASE_PASSWORD,
        db_uri=param.DATABASE_URL,
        database=param.DATABASE_NAME,
    )

    def test_show_schema(self):
        result = self.neo4j_tools.show_schema()
        assert isinstance(result, str)
        print(result)

    def test_show_labels(self):
        result = self.neo4j_tools.show_labels()
        assert isinstance(result, str)
        print(result)

    def test_show_relationships(self):
        result = self.neo4j_tools.show_relationships()
        assert isinstance(result, str)
        print(result)

    def test_execute_cypher_1(self):
        result = self.neo4j_tools.execute_cypher(
            cypher="MATCH p=()-[r:CONTAINS]->() RETURN p LIMIT 3"
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_cypher_2(self):
        result = self.neo4j_tools.execute_cypher(
            cypher="MATCH (n:系统组件:主机) RETURN n LIMIT 3"
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_cypher_3(self):
        result = self.neo4j_tools.execute_cypher(
            cypher=dedent(
                """\
                MATCH (n) WHERE (n.`中间件服务地址`) IS NOT NULL 
                RETURN DISTINCT "node" as entity, n.`中间件服务地址` AS `中间件服务地址` LIMIT 25 
                UNION ALL 
                MATCH ()-[r]-() WHERE (r.`中间件服务地址`) IS NOT NULL 
                RETURN DISTINCT "relationship" AS entity, r.`中间件服务地址` AS `中间件服务地址` LIMIT 25\
            """
            )
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_cypher_4(self):
        result = self.neo4j_tools.execute_cypher(
            cypher=dedent(
                """\
                MATCH (system:System {name: '数智信通'})-[:RELATES_TO]->(component)
                RETURN component\
                """
            )
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_cypher_5(self):
        result = self.neo4j_tools.execute_cypher(
            cypher=dedent(
                """MATCH (sys:系统资源 {系统资源名称: '数智信通'})--(relatedNodes) RETURN sys, r, relatedNodes)"""
            )
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_cypher_path_0(self):
        result = self.neo4j_tools.execute_cypher(
            cypher=dedent(
                """\
                MATCH p = (a)-[*1..5]-(b)
                WHERE a.name = '智能一体化运维支撑平台' AND b.name = '智能一体化运维支撑平台oracle主库生产环境数据源'
                RETURN p, nodes(p) AS path_nodes, relationships(p) AS relationships\
                """
            )
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_cypher_path_1(self):
        result = self.neo4j_tools.execute_cypher(
            cypher=dedent(
                """\
                MATCH (n1 {name: '智能一体化运维支撑平台'})-[:RELATIONSHIP]->(n2 {name:'智能一体化运维支撑平台oracle主库生产环境数据源'})
                RETURN n1, n2, type(RELATIONSHIP)\
                """
            )
        )
        assert isinstance(result, str)
        print(result)

    def test_count(self):
        result = self.neo4j_tools.execute_cypher(cypher=dedent(""":schema"""))
        assert isinstance(result, str)
        print(result)
