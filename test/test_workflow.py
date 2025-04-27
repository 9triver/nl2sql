import sys, os

sys.path.insert(0, os.path.abspath("../src"))

from workflow.nl2cypher import NL2CypherWorkflow
from agno.utils.pprint import pprint_run_response


class TestWorkflow:
    workflow = NL2CypherWorkflow()

    def test_question_0(self):
        response = self.workflow.run(question="数智信通这个系统的信息", retries=0)
        pprint_run_response(response, markdown=True)

    def test_question_1(self):
        response = self.workflow.run(
            question="数智信通这个系统包含哪些组件？", retries=0
        )
        pprint_run_response(response, markdown=True)

    def test_question_2(self):
        response = self.workflow.run(
            question="名为‘智能一体化运维支撑平台‘和’智能一体化运维支撑平台oracle主库生产环境数据源‘两个节点之间有多少条节点数少于5的路径？",
            retries=0,
        )
        pprint_run_response(response, markdown=True)
