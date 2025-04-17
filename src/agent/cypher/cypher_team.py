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

from agno.knowledge.agent import AgentKnowledge
from agno.memory.v2.memory import Memory
from pydantic import BaseModel
from agno.agent import Agent
from agno.team.team import Team
from agno.models.base import Model
from agno.memory.team import TeamMemory
from agno.storage.base import Storage
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from storage.yaml import YamlStorage
from tools.baidu_search import BaiduSearchTools
from tools.cypher_knowledge import CypherKnowledge
from tools.neq4j import Neo4jTools
from param import Parameter


class CypherTeam(Team):
    name = "cypher-team"
    description = dedent("""You are the leader of a Cypher Statement Team.""")
    instructions = dedent(
        """\
        - Decompose the task into small sub-tasks. You can only execute the cypher statement generated by members.
        - Follow and Print the **Thought-Act-Observation** chain-of-thought traces:
            1. **Thought**: Reason based on the user question and previous observations.
            2. **Act**: Choose One Action to do it:
                Act 1.Use tools
                Act 2.Generate a cypher statement to find any infomation you want to know. Notice: Infomation in Database is in Chinese.
                Act 3.Refine the previous cypher statement.
                Act 4.Assign subtasks to team members.
            3. **Observation**: Analyse the result of previous act.
        - Continue the **Thought-Act-Observation** loop until: You are confident that you can answer the user's question.
        - Print And Answer in Chinese. But don't translate the infomation in database.\
    """
    )
    success_criteria = dedent(
        """Answer user's question in detail based on the real data in the neo4j database."""
    )
    database_dir = "./tmp"

    def __init__(
        self,
        param: Parameter,
        members: List[Union[Agent, "Team"]],
        mode: Literal["route", "coordinate", "collaborate"] = "coordinate",
        model: Optional[Model] = None,
        name: Optional[str] = name,
        team_id: Optional[str] = name,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
        session_state: Optional[Dict[str, Any]] = None,
        add_state_in_messages: bool = False,
        description: Optional[str] = description,
        instructions: Optional[Union[str, List[str], Callable]] = instructions,
        expected_output: Optional[str] = None,
        additional_context: Optional[str] = None,
        success_criteria: Optional[str] = None,
        markdown: bool = True,
        add_datetime_to_instructions: bool = False,
        add_member_tools_to_system_message: bool = False,
        context: Optional[Dict[str, Any]] = None,
        add_context: bool = False,
        knowledge: Optional[AgentKnowledge] = None,
        retriever: Optional[Callable[..., Optional[List[Dict]]]] = None,
        references_format: Literal["json", "yaml"] = "json",
        enable_agentic_context: bool = False,
        share_member_interactions: bool = False,
        get_member_information_tool: bool = True,
        search_knowledge: bool = False,
        read_team_history: bool = True,
        tools: Optional[List[Union[Toolkit, Callable, Function, Dict]]] = None,
        show_tool_calls: bool = True,
        tool_call_limit: Optional[int] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        use_json_mode: bool = False,
        parse_response: bool = False,
        memory: Optional[Union[TeamMemory, Memory]] = None,
        enable_agentic_memory: bool = False,
        enable_user_memories: bool = False,
        add_memory_references: Optional[bool] = None,
        enable_session_summaries: bool = False,
        add_session_summary_references: Optional[bool] = None,
        enable_team_history: bool = True,
        num_of_interactions_from_history: int = 2,
        storage: Optional[Storage] = YamlStorage(
            dir_path=os.path.join(database_dir, "team_storage"), mode="team"
        ),
        extra_data: Optional[Dict[str, Any]] = None,
        reasoning: bool = False,
        reasoning_model: Optional[Model] = None,
        reasoning_min_steps: int = 1,
        reasoning_max_steps: int = 10,
        debug_mode: bool = True,
        show_members_responses: bool = True,
        monitoring: bool = False,
        telemetry: bool = False,
    ):
        if tools is None:
            tools = [
                CypherKnowledge(),
                BaiduSearchTools(),
                Neo4jTools(
                    user=param.DATABASE_USER,
                    password=param.DATABASE_PASSWORD,
                    db_uri=param.DATABASE_URL,
                    database=param.DATABASE_NAME,
                    syntax=True,
                    execution=True,
                    labels=True,
                    relationships=True,
                ),
            ]
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
            additional_context=additional_context,
            success_criteria=success_criteria,
            markdown=markdown,
            add_datetime_to_instructions=add_datetime_to_instructions,
            add_member_tools_to_system_message=add_member_tools_to_system_message,
            context=context,
            add_context=add_context,
            knowledge=knowledge,
            retriever=retriever,
            references_format=references_format,
            enable_agentic_context=enable_agentic_context,
            share_member_interactions=share_member_interactions,
            get_member_information_tool=get_member_information_tool,
            search_knowledge=search_knowledge,
            read_team_history=read_team_history,
            tools=tools,
            show_tool_calls=show_tool_calls,
            tool_call_limit=tool_call_limit,
            tool_choice=tool_choice,
            response_model=response_model,
            use_json_mode=use_json_mode,
            parse_response=parse_response,
            memory=memory,
            enable_agentic_memory=enable_agentic_memory,
            enable_user_memories=enable_user_memories,
            add_memory_references=add_memory_references,
            enable_session_summaries=enable_session_summaries,
            add_session_summary_references=add_session_summary_references,
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
