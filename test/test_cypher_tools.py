import sys, os

sys.path.insert(0, os.path.abspath("../src"))
from textwrap import dedent
from tools.cypher import CypherTools
from param import Parameter


class TestCypherTools:
    param = Parameter(config_file_path="../config.yaml")
    cypher_tools = CypherTools(
        embed_model_name=param.embed_model_name,
        embed_base_url=param.embed_base_url,
        embed_api_key=param.embed_api_key,
    )

    def test_normalize_cypher_1(self):
        normalized_cypher = self.cypher_tools.normalize_cypher(
            cypher="MATCH p=()-[r:CONTAINS]->() RETURN p LIMIT 3"
        )
        assert isinstance(normalized_cypher, str)
        print(f"\n{normalized_cypher}\n")

    def test_normalize_cypher_2(self):
        normalized_cypher = self.cypher_tools.normalize_cypher(
            cypher="MATCH (n:系统组件:主机) RETURN n LIMIT 3"
        )
        assert isinstance(normalized_cypher, str)
        print(f"\n{normalized_cypher}\n")

    def test_normalize_cypher_3(self):
        normalized_cypher = self.cypher_tools.normalize_cypher(
            cypher="""MATCH (n) WHERE (n.`中间件服务地址`) IS NOT NULL 
                RETURN DISTINCT "node" as entity, n.`中间件服务地址` AS `中间件服务地址` LIMIT 25 
                UNION ALL 
                MATCH ()-[r]-() WHERE (r.`中间件服务地址`) IS NOT NULL 
                RETURN DISTINCT "relationship" AS entity, r.`中间件服务地址` AS `中间件服务地址` LIMIT 25
            """
        )
        assert isinstance(normalized_cypher, str)
        print(f"\n{normalized_cypher}\n")

    def test_normalize_cypher_4(self):
        normalized_cypher = self.cypher_tools.normalize_cypher(
            cypher=dedent(
                """\
                MATCH (system:System {name: '数智信通'})-[:RELATES_TO]->(component)
                RETURN component\
                """
            )
        )
        assert isinstance(normalized_cypher, str)
        print(f"\n{normalized_cypher}\n")

    def test_normalize_cypher_5(self):
        normalized_cypher = self.cypher_tools.normalize_cypher(
            cypher=dedent(
                """MATCH (sys:系统资源 {系统资源名称: '数智信通'})--(relatedNodes) RETURN sys, r, relatedNodes)"""
            )
        )
        assert isinstance(normalized_cypher, str)
        print(f"\n{normalized_cypher}\n")

    def test_normalize_cypher_path_0(self):
        normalized_cypher = self.cypher_tools.normalize_cypher(
            cypher=dedent(
                """\
                MATCH p = (a)-[*1..5]-(b)
                WHERE a.name = '智能一体化运维支撑平台' AND b.name = '智能一体化运维支撑平台oracle主库生产环境数据源'
                RETURN p, nodes(p) AS path_nodes, relationships(p) AS relationships\
                """
            )
        )
        assert isinstance(normalized_cypher, str)
        print(f"\n{normalized_cypher}\n")

    def test_normalize_cypher_path_1(self):
        normalized_cypher = self.cypher_tools.normalize_cypher(
            cypher=dedent(
                """\
                MATCH (n1 {name: '智能一体化运维支撑平台'})-[:RELATIONSHIP]->(n2 {name:'智能一体化运维支撑平台oracle主库生产环境数据源'})
                RETURN n1, n2, type(RELATIONSHIP)\
                """
            )
        )
        assert isinstance(normalized_cypher, str)
        print(f"\n{normalized_cypher}\n")
