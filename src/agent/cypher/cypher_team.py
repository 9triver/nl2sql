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
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from pydantic import BaseModel
from agno.models.base import Model
from agno.storage.base import Storage
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit

from storage.yaml import YamlStorage
from tools.neq4j import Neo4jTools
from tools.cypher import CypherTools
from param import Parameter
from base.agent import Agent
from base.team import Team
from base.memory.manager import MemoryManager
from base.memory.team import TeamMemory


class CypherTeam(Team):
    name = "cypher-team"
    description = dedent("""Cypher 语句专家团队负责人""")
    instructions = dedent(
        """\
        - 将复杂任务拆解为多个子任务。
        - 用户提供的信息不准确，因此写cypher语句前先收集信息：例如映射实体、查看标签/关系等
        - 严格遵循并打印 **思考-行动-观察** 的思维链流程：
            1. **思考**：基于用户问题和之前的观察结果进行推理
            2. **行动**：选择以下一个操作执行：
                - 将子任务分配给成员
                - 生成/优化cypher语句
            3. **观察**：分析上一步行动的执行结果
        - 持续循环 **思考-行动-观察** 流程，直到：确信可以准确回答用户问题
        - 回答时不要翻译数据库中的原始信息（保持数据库信息原文）\
    """
    )
    database_dir = "./tmp"
    storage = YamlStorage(dir_path=os.path.join(database_dir, "team"), mode="team")
    memory = TeamMemory(
        member_interaction_num=3,
        db=SqliteMemoryDb(
            table_name="team",
            db_file=os.path.join(database_dir, "team/memory.db"),
        ),
        manager=MemoryManager(),
    )

    def __init__(
        self,
        param: Parameter,
        members: List[Union[Agent, "Team"]],
        mode: Literal["route", "coordinate", "collaborate"] = "coordinate",
        model: Optional[Model] = None,
        name: Optional[str] = name,
        team_id: Optional[str] = None,
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
        share_member_interactions: bool = True,
        get_member_information_tool: bool = False,
        search_knowledge: bool = False,
        read_team_history: bool = True,
        tools: Optional[List[Union[Toolkit, Callable, Function, Dict]]] = None,
        show_tool_calls: bool = True,
        tool_call_limit: Optional[int] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        tool_hooks: Optional[List[Callable]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        use_json_mode: bool = False,
        parse_response: bool = False,
        memory: Optional[Union[TeamMemory, Memory]] = memory,
        enable_agentic_memory: bool = False,
        enable_user_memories: bool = False,
        add_memory_references: Optional[bool] = False,
        enable_session_summaries: bool = False,
        add_session_summary_references: Optional[bool] = False,
        enable_team_history: bool = True,
        num_of_interactions_from_history: int = None,
        num_history_runs: int = 3,
        storage: Optional[Storage] = storage,
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
                Neo4jTools(
                    user=param.DATABASE_USER,
                    password=param.DATABASE_PASSWORD,
                    db_uri=param.DATABASE_URL,
                    database=param.DATABASE_NAME,
                    embed_model_name=param.embed_model_name,
                    embed_base_url=param.embed_base_url,
                    embed_api_key=param.embed_api_key,
                    schema=True,
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
            tool_hooks=tool_hooks,
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
            num_history_runs=num_history_runs,
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
