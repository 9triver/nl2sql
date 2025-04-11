from prompt_toolkit import PromptSession
from agent.cypher.cypher_team import CypherTeam
from agent.cypher.cypher_generator import CypherGeneratorAgent
from param import Parameter
from utils.utils import get_model

if __name__ == "__main__":
    param = Parameter(config_file_path="./config.yaml")
    model = get_model(
        api_key=param.model_api_key,
        base_url=param.model_base_url,
        model_name=param.model_name,
    )
    cypher_generator = CypherGeneratorAgent(param=param, model=model)
    cypher_team = CypherTeam(param=param, model=model, members=[cypher_generator])
    session = PromptSession("输入你的问题或输入Q退出\n🧑")
    while True:
        message = session.prompt()
        if len(message) == 0:
            continue
        if message == "Q":
            break
        cypher_team.print_response(message=message, stream=True)
