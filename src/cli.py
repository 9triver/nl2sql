from prompt_toolkit import PromptSession
from workflow.nl2cypher import NL2CypherWorkflow
from agno.utils.pprint import pprint_run_response
from loguru import logger

if __name__ == "__main__":
    workflow = NL2CypherWorkflow()
    session = PromptSession("输入你的问题或输入Q退出\n🧑")
    while True:
        message = session.prompt()
        if len(message) == 0:
            continue
        if message == "Q":
            break
        run_response = workflow.run(question=message)
        pprint_run_response(run_response=run_response, markdown=True, show_time=True)
