from agno.models.openai import OpenAILike
from agent.cypher.cypher_team import CypherTeam
from agent.cypher.entity_specifier import EntitySpecifierAgent
from agent.question_validator import QuestionValidatorAgent
from param import Parameter


def get_model(api_key: str, base_url: str, model_name: str):
    return OpenAILike(id=model_name, base_url=base_url, api_key=api_key)


param = Parameter(config_file_path="./config.yaml")
model = get_model(
    api_key=param.model_api_key,
    base_url=param.model_base_url,
    model_name=param.model_name,
)


def get_cypher_team():
    entity_specifier = EntitySpecifierAgent(param=param, model=model, retries=100)
    question_validator = QuestionValidatorAgent(model=model, retries=100)
    cypher_team = CypherTeam(
        param=param, model=model, members=[entity_specifier, question_validator]
    )
    return cypher_team


def get_validator():
    question_validator = QuestionValidatorAgent(model=model, retries=100)
    return question_validator
