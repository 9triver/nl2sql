import os
from textwrap import dedent
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Type,
    Union,
)
from os import getenv

from pydantic import BaseModel
from agno.agent import Agent
from agno.team.team import Team
from agno.models.base import Model
from agno.models.openai import OpenAILike
from agno.memory.team import TeamMemory
from agno.storage.base import Storage
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from agno.storage.json import JsonStorage

from .cypher_generator import CypherGeneratorAgent
from tools.neq4j import Neo4jTools

from utils.utils import DATABASE_URL, USER, PASSWORD, NEO4J_DATABASE


class CypherTeam(Team):
    # model = OpenAILike(
    #     id="DeepSeek-R1",
    #     base_url="https://api.sensenova.cn/compatible-mode/v1/",
    #     api_key=getenv("SENSETIME_API_KEY"),
    # )
    model = OpenAILike(
        id="Qwen/Qwen2.5-32B-Instruct",
        base_url="https://api-inference.modelscope.cn/v1/",
        api_key=getenv("MODELSCOPE_API_KEY"),
    )
    description = dedent("""You are the leader of a Cypher Statement Team.""")
    instructions = dedent(
        """\
        - Decompose the task into small sub-tasks.
        - Follow and Print the **Thought-Act-Observation** chain-of-thought traces:
            1. **Thought**: Reason based on the user question and previous observations.
            2. **Act**: Assign subtasks to team members, Or Use one tool.
            3. **Observation**: Analyse the result of previous act.
        - Continue the **Thought-Act-Observation** loop until:
            1. You are confident that you can answer the user's question.
            2. Or You think the user should provide more infomation.
        - Print And Answer in Chinese. But don't translate the infomation in database.\
    """
    )
    success_criteria = dedent(
        """Answer user's question in detail based on the real data in the neo4j database."""
    )

    cypher_generator: CypherGeneratorAgent = CypherGeneratorAgent()
    database_dir = "./tmp"

    def __init__(
        self,
        members: List[Union[Agent, "Team"]] = [cypher_generator],
        mode: Literal["route", "coordinate", "collaborate"] = "coordinate",
        model: Optional[Model] = model,
        name: Optional[str] = "Cypher Team",
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
        session_state: Optional[Dict[str, Any]] = None,
        add_state_in_messages: bool = False,
        description: Optional[str] = description,
        instructions: Optional[Union[str, List[str], Callable]] = instructions,
        expected_output: Optional[str] = None,
        success_criteria: Optional[str] = None,
        markdown: bool = True,
        add_datetime_to_instructions: bool = False,
        context: Optional[Dict[str, Any]] = None,
        add_context: bool = False,
        enable_agentic_context: bool = True,
        share_member_interactions: bool = True,
        read_team_history: bool = True,
        tools: Optional[List[Union[Toolkit, Callable, Function, Dict]]] = [
            Neo4jTools(
                user=USER,
                password=PASSWORD,
                db_uri=DATABASE_URL,
                database=NEO4J_DATABASE,
            )
        ],
        show_tool_calls: bool = True,
        tool_call_limit: Optional[int] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        use_json_mode: bool = False,
        parse_response: bool = True,
        memory: Optional[TeamMemory] = None,
        enable_team_history: bool = True,
        num_of_interactions_from_history: int = 3,
        storage: Optional[Storage] = JsonStorage(
            mode="team",
            dir_path=os.path.join(database_dir, "team_storage"),
        ),
        extra_data: Optional[Dict[str, Any]] = None,
        reasoning: bool = False,
        reasoning_model: Optional[Model] = None,
        reasoning_min_steps: int = 1,
        reasoning_max_steps: int = 10,
        debug_mode: bool = True,
        show_members_responses: bool = False,
        monitoring: bool = False,
        telemetry: bool = True,
    ):
        super().__init__(
            members=members,
            mode=mode,
            model=model,
            name=name,
            team_id=team_id,
            user_id=user_id,
            session_id=session_id,
            session_name=session_name,
            session_state=session_state,
            add_state_in_messages=add_state_in_messages,
            description=description,
            instructions=instructions,
            expected_output=expected_output,
            success_criteria=success_criteria,
            markdown=markdown,
            add_datetime_to_instructions=add_datetime_to_instructions,
            context=context,
            add_context=add_context,
            enable_agentic_context=enable_agentic_context,
            share_member_interactions=share_member_interactions,
            read_team_history=read_team_history,
            tools=tools,
            show_tool_calls=show_tool_calls,
            tool_call_limit=tool_call_limit,
            tool_choice=tool_choice,
            response_model=response_model,
            use_json_mode=use_json_mode,
            parse_response=parse_response,
            memory=memory,
            enable_team_history=enable_team_history,
            num_of_interactions_from_history=num_of_interactions_from_history,
            storage=storage,
            extra_data=extra_data,
            reasoning=reasoning,
            reasoning_model=reasoning_model,
            reasoning_min_steps=reasoning_min_steps,
            reasoning_max_steps=reasoning_max_steps,
            debug_mode=debug_mode,
            show_members_responses=show_members_responses,
            monitoring=monitoring,
            telemetry=telemetry,
        )
