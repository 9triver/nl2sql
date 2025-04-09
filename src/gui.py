from agent.cypher.cypher_team import CypherTeam
from agent.cypher.cypher_generator import CypherGeneratorAgent
from param import Parameter
from ui.chatui import ChatUI
from loguru import logger

if __name__ == "__main__":
    param = Parameter(config_file_path="./config.yaml")
    cypher_generator = CypherGeneratorAgent(param=param)
    cypher_team = CypherTeam(param=param, members=[cypher_generator])
    chatui = ChatUI(cypher_team=cypher_team)
    chatui.run()
