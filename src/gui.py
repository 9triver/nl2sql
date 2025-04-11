from agent.cypher.cypher_team import CypherTeam
from agent.cypher.cypher_generator import CypherGeneratorAgent
from param import Parameter
from utils.utils import get_model
from ui.chatui import ChatUI
from loguru import logger

if __name__ == "__main__":
    param = Parameter(config_file_path="./config.yaml")
    model = get_model(
        api_key=param.model_api_key,
        base_url=param.model_base_url,
        model_name=param.model_name,
    )
    cypher_generator = CypherGeneratorAgent(param=param, model=model)
    cypher_team = CypherTeam(param=param, model=model, members=[cypher_generator])
    chatui = ChatUI(cypher_team=cypher_team)
    chatui.run()
