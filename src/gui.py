from ui.chatui import ChatUI
from agent.cypher.cypher_team import CypherTeam
from loguru import logger

if __name__ == "__main__":
    chatui = ChatUI(cypher_team=CypherTeam())
    chatui.run()
