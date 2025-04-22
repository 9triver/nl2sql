from workflow.nl2cypher import NL2CypherWorkflow
from ui.chatui import ChatUI
from loguru import logger

if __name__ == "__main__":
    workflow = NL2CypherWorkflow()
    chatui = ChatUI(workflow=workflow)
    chatui.run()
