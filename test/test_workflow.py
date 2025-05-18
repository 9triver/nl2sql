import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

from agno.utils.pprint import pprint_run_response

from workflow.nl2cypher import NL2CypherWorkflow


class TestWorkflow:
    workflow = NL2CypherWorkflow()

    def test_question_0(self):
        response = self.workflow.run(question="数智信通这个系统的信息")
        pprint_run_response(response, markdown=True)

    def test_question_1(self):
        response = self.workflow.run(question="数智信通这个系统包含哪些组件？")
        pprint_run_response(response, markdown=True)

    def test_question_2(self):
        response = self.workflow.run(
            question="智能一体化运维支撑平台和一体化运维支撑平台oracle生产数据源两个节点之间有多少条节点数不超过5的路径？"
        )
        pprint_run_response(response, markdown=True)
