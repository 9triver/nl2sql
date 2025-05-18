from ui.chatui import ChatUI
from workflow.nl2cypher import NL2CypherWorkflow

if __name__ == "__main__":
    workflow = NL2CypherWorkflow()
    chatui = ChatUI(workflow=workflow)
    chatui.run()
