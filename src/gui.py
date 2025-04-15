from utils.utils import get_cypher_team
from ui.chatui import ChatUI
from loguru import logger

if __name__ == "__main__":
    cypher_team = get_cypher_team()
    chatui = ChatUI(cypher_team=cypher_team)
    chatui.run()
