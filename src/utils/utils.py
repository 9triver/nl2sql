from agno.models.openai import OpenAILike
from agent.cypher.cypher_team import CypherTeam
from agent.cypher.intent_specifier import IntentSpecifierAgent
from agent.cypher.cypher_generator import CypherGeneratorExecutorAgent
from param import Parameter


def get_model(api_key: str, base_url: str, model_name: str):
    return OpenAILike(id=model_name, base_url=base_url, api_key=api_key)


def get_cypher_team():
    param = Parameter(config_file_path="./config.yaml")
    model = get_model(
        api_key=param.model_api_key,
        base_url=param.model_base_url,
        model_name=param.model_name,
    )
    intent_specifier = IntentSpecifierAgent(param=param, model=model, retries=100)
    cypher_team = CypherTeam(param=param, model=model, members=[intent_specifier])
    return cypher_team
