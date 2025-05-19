import json
from typing import Union

from agno.models.openai import OpenAILike
from agno.run.response import RunResponse
from agno.run.team import TeamRunResponse
from pydantic import BaseModel

from agent.cypher.cypher_team import CypherTeam
from agent.cypher.cypher_tree_team import CypherTreeTeam
from agent.cypher.entity_specifier import EntitySpecifierAgent
from agent.reflector import ReflectorAgent
from param import Parameter
from tools.cypher import CypherTools
from tools.neq4j import Neo4jTools

param = Parameter(config_file_path="./config.yaml")


def get_model(temperature: float = 1.0, enable_thinking: bool = False):
    return OpenAILike(
        id=param.response_model_name,
        base_url=param.response_base_url,
        api_key=param.response_api_key,
        request_params={
            "extra_body": {
                "enable_thinking": enable_thinking,
            }
        },
        temperature=temperature,
    )


def get_cypher_team():
    entity_specifier = EntitySpecifierAgent(
        param=param,
        model=get_model(temperature=0.4),
        retries=3,
    )
    cypher_team = CypherTeam(
        param=param,
        model=get_model(temperature=0.4),
        members=[entity_specifier],
    )
    return cypher_team


team_tools = [
    CypherTools(
        embed_model_name=param.embed_model_name,
        embed_base_url=param.embed_base_url,
        embed_api_key=param.embed_api_key,
    ),
    Neo4jTools(
        user=param.DATABASE_USER,
        password=param.DATABASE_PASSWORD,
        db_uri=param.DATABASE_URL,
        database=param.DATABASE_NAME,
        embed_model_name=param.embed_model_name,
        embed_base_url=param.embed_base_url,
        embed_api_key=param.embed_api_key,
        labels=True,
        relationships=True,
        execution=True,
    ),
]


def get_cypher_tree_team():
    entity_specifier = EntitySpecifierAgent(
        param=param,
        model=get_model(temperature=0.2),
        retries=3,
    )
    cypher_tree_team = CypherTreeTeam(
        param=param,
        model=get_model(temperature=0.8),
        tools=team_tools,
        members=[entity_specifier],
    )
    return cypher_tree_team


def get_reflector():
    reflector = ReflectorAgent(
        model=get_model(temperature=0.2),
        retries=3,
    )
    return reflector


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
