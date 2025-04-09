from agent.cypher.cypher_team import CypherTeam
from agent.cypher.cypher_generator import CypherGeneratorAgent
from agent.cypher.intent_specifier import IntentSpecifierAgent
from param import Parameter
from prompt_toolkit import PromptSession

if __name__ == "__main__":
    param = Parameter(config_file_path="./config.yaml")
    cypher_generator = CypherGeneratorAgent(param=param)
    # intent_specifier = IntentSpecifierAgent(param=param)
    cypher_team = CypherTeam(param=param, members=[cypher_generator])
    session = PromptSession("输入你的问题或输入Q退出\n🧑")
    while True:
        message = session.prompt()
        if len(message) == 0:
            continue
        if message == "Q":
            break
        cypher_team.print_response(message=message, stream=True)
