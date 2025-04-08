import sys, os

sys.path.insert(0, os.path.abspath("../src"))
from textwrap import dedent
from tools.neq4j import Neo4jTools
from utils.utils import DATABASE_URL, USER, PASSWORD, NEO4J_DATABASE


class TestNeo4jTools:
    neo4j_tools = Neo4jTools(
        user=USER,
        password=PASSWORD,
        db_uri=DATABASE_URL,
        database=NEO4J_DATABASE,
    )

    def test_show_indexes(self):
        result = self.neo4j_tools.show_indexes()
        assert isinstance(result, str)
        print(result)

    def test_show_metadata(self):
        result = self.neo4j_tools.show_metadata()
        assert isinstance(result, str)
        print(result)

    def test_execute_query_1(self):
        result = self.neo4j_tools.execute_query(
            query="MATCH p=()-[r:CONTAINS]->() RETURN p LIMIT 3"
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_query_2(self):
        result = self.neo4j_tools.execute_query(
            query="MATCH (n:系统组件:主机) RETURN n LIMIT 3"
        )
        assert isinstance(result, str)
        print(result)

    def test_execute_query_3(self):
        result = self.neo4j_tools.execute_query(
            query=dedent(
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
