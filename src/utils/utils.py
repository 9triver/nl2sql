import json
from typing import Union
from pydantic import BaseModel
from agno.models.openai import OpenAILike
from agno.run.response import RunResponse
from agno.run.team import TeamRunResponse

from agent.cypher.cypher_team import CypherTeam
from agent.cypher.entity_specifier import EntitySpecifierAgent
from agent.question_validator import QuestionValidatorAgent
from param import Parameter


def get_model(api_key: str, base_url: str, response_model_name: str):
    return OpenAILike(
        id=response_model_name,
        base_url=base_url,
        api_key=api_key,
        request_params={
            "extra_body": {
                "enable_thinking": False,
            }
        },
    )


param = Parameter(config_file_path="./config.yaml")
model = get_model(
    api_key=param.response_api_key,
    base_url=param.response_base_url,
    response_model_name=param.response_model_name,
)


def get_cypher_team():
    entity_specifier = EntitySpecifierAgent(param=param, model=model, retries=3)
    # question_validator = QuestionValidatorAgent(model=model, retries=3)
    cypher_team = CypherTeam(param=param, model=model, members=[entity_specifier])
    return cypher_team


def get_validator():
    question_validator = QuestionValidatorAgent(model=model, retries=3)
    return question_validator


def get_validate_message(question: str, response: str):
    return f"问题: {question}\n回答: {response}"


def get_run_response_content(run_response: Union[RunResponse, TeamRunResponse]):
    if run_response is None:
        return ""

    single_response_content = ""
    if isinstance(run_response.content, str):
        single_response_content = run_response.get_content_as_string(indent=4)
    elif isinstance(run_response.content, BaseModel):
        single_response_content = run_response.content.model_dump_json(
            exclude_none=True
        )
    else:
        single_response_content = json.dumps(
            obj=run_response.content, ensure_ascii=False, indent=2
        )
    return single_response_content


def get_run_response(run_response: Union[RunResponse, TeamRunResponse]):
    run_response_content = get_run_response_content(run_response=run_response)

    member_responses = None
    formatted_tool_calls = None
    if isinstance(run_response, TeamRunResponse):
        member_responses = run_response.member_responses
        formatted_tool_calls = run_response.formatted_tool_calls

    other_message = ""
    if member_responses is not None and len(member_responses) > 0:
        member_messages = [
            get_run_response_content(run_response=member_response)
            for member_response in member_responses
        ]
        member_messages = "成员回答:\n" + "\n".join(member_messages) + "\n"
        other_message += member_messages
    if formatted_tool_calls is not None:
        tool_used_messages = "使用工具:\n" + "\n".join(formatted_tool_calls) + "\n"
        other_message += tool_used_messages

    return run_response_content, other_message
