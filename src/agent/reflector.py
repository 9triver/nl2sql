from textwrap import dedent
from typing import Any, Callable, Dict, List, Literal, Optional, Type, Union

from agno.knowledge.agent import AgentKnowledge
from agno.memory.agent import AgentMemory
from agno.memory.v2.memory import Memory
from agno.models.base import Model
from agno.models.message import Message
from agno.storage.base import Storage
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from pydantic import BaseModel, Field

from base.agent import Agent


class Reflection(BaseModel):
    plan: str = Field(description="对推理中间状态的分析评价，以及下一步的计划")
    score: int = Field(
        description="对候选推理中间状态质量的评分，范围0-10分",
        gte=0,
        lte=10,
    )
    end: bool = Field(description="推理中间状态是否达到推理终止点(无需进一步推理)")

    def __repr__(self):
        return f"Reflection(plan='{self.plan}', score={self.score}, end={self.end})"

    def as_message(self) -> str:
        return f"分析与计划: {self.plan}\n评分: {self.score}"

    @property
    def normalized_score(self) -> float:
        return self.score / 10.0


class ReflectorAgent(Agent):
    name = ("reflection-agent",)
    system_message = ("你是一个能够对推理中间状态进行反思和评分的AI助手。",)
    role = None
    description = None
    instructions = None

    @staticmethod
    def get_prompt():
        return dedent("""\
            请对以下用户问题和当前中间推理状态进行反思和评分。
            用户问题：{input}
            中间推理状态：{candidate}

            请按照以下格式提供你的反思：
            计划：[你的详细分析和下一步计划]
            评分：[0-10分的评分]
            终止：[是/否]\
            """)

    def __init__(
        self,
        *,
        model: Optional[Model] = None,
        name: Optional[str] = name,
        agent_id: Optional[str] = None,
        introduction: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
        session_state: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        add_context: bool = False,
        resolve_context: bool = True,
        memory: Optional[Union[AgentMemory, Memory]] = None,
        enable_agentic_memory: bool = False,
        enable_user_memories: bool = False,
        add_memory_references: Optional[bool] = None,
        enable_session_summaries: bool = False,
        add_session_summary_references: Optional[bool] = None,
        add_history_to_messages: bool = False,
        num_history_responses: Optional[int] = None,
        num_history_runs: int = 3,
        knowledge: Optional[AgentKnowledge] = None,
        add_references: bool = False,
        retriever: Optional[Callable[..., Optional[List[Dict]]]] = None,
        references_format: Literal["json", "yaml"] = "json",
        storage: Optional[Storage] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Union[Toolkit, Callable, Function, Dict]]] = None,
        show_tool_calls: bool = False,
        tool_call_limit: Optional[int] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        tool_hooks: Optional[List[Callable]] = None,
        reasoning: bool = False,
        reasoning_model: Optional[Model] = None,
        reasoning_agent: Optional[Agent] = None,
        reasoning_min_steps: int = 1,
        reasoning_max_steps: int = 10,
        read_chat_history: bool = False,
        search_knowledge: bool = False,
        update_knowledge: bool = False,
        read_tool_call_history: bool = False,
        system_message: Optional[Union[str, Callable, Message]] = system_message,
        system_message_role: str = "system",
        create_default_system_message: bool = False,
        description: Optional[str] = description,
        goal: Optional[str] = None,
        instructions: Optional[Union[str, List[str], Callable]] = instructions,
        expected_output: Optional[str] = None,
        additional_context: Optional[str] = None,
        markdown: bool = False,
        add_name_to_instructions: bool = True,
        add_datetime_to_instructions: bool = False,
        timezone_identifier: Optional[str] = None,
        add_state_in_messages: bool = False,
        add_messages: Optional[List[Union[Dict, Message]]] = None,
        user_message: Optional[Union[List, Dict, str, Callable, Message]] = None,
        user_message_role: str = "user",
        create_default_user_message: bool = False,
        retries: int = 3,
        delay_between_retries: int = 1,
        exponential_backoff: bool = False,
        response_model: Optional[Type[BaseModel]] = Reflection,
        parse_response: bool = True,
        structured_outputs: Optional[bool] = None,
        use_json_mode: bool = True,
        save_response_to_file: Optional[str] = None,
        stream: Optional[bool] = False,
        stream_intermediate_steps: bool = False,
        team: Optional[List[Agent]] = None,
        team_data: Optional[Dict[str, Any]] = None,
        role: Optional[str] = role,
        respond_directly: bool = False,
        add_transfer_instructions: bool = False,
        team_response_separator: str = "\n",
        debug_mode: bool = True,
        monitoring: bool = False,
        telemetry: bool = False,
    ):
        super().__init__(
            model=model,
            name=name,
            agent_id=agent_id,
            introduction=introduction,
            user_id=user_id,
            session_id=session_id,
            session_name=session_name,
            session_state=session_state,
            context=context,
            add_context=add_context,
            resolve_context=resolve_context,
            memory=memory,
            enable_agentic_memory=enable_agentic_memory,
            enable_user_memories=enable_user_memories,
            add_memory_references=add_memory_references,
            enable_session_summaries=enable_session_summaries,
            add_session_summary_references=add_session_summary_references,
            add_history_to_messages=add_history_to_messages,
            num_history_responses=num_history_responses,
            num_history_runs=num_history_runs,
            knowledge=knowledge,
            add_references=add_references,
            retriever=retriever,
            references_format=references_format,
            storage=storage,
            extra_data=extra_data,
            tools=tools,
            show_tool_calls=show_tool_calls,
            tool_call_limit=tool_call_limit,
            tool_choice=tool_choice,
            tool_hooks=tool_hooks,
            reasoning=reasoning,
            reasoning_model=reasoning_model,
            reasoning_agent=reasoning_agent,
            reasoning_min_steps=reasoning_min_steps,
            reasoning_max_steps=reasoning_max_steps,
            read_chat_history=read_chat_history,
            search_knowledge=search_knowledge,
            update_knowledge=update_knowledge,
            read_tool_call_history=read_tool_call_history,
            system_message=system_message,
            system_message_role=system_message_role,
            create_default_system_message=create_default_system_message,
            description=description,
            goal=goal,
            instructions=instructions,
            expected_output=expected_output,
            additional_context=additional_context,
            markdown=markdown,
            add_name_to_instructions=add_name_to_instructions,
            add_datetime_to_instructions=add_datetime_to_instructions,
            timezone_identifier=timezone_identifier,
            add_state_in_messages=add_state_in_messages,
            add_messages=add_messages,
            user_message=user_message,
            user_message_role=user_message_role,
            create_default_user_message=create_default_user_message,
            retries=retries,
            delay_between_retries=delay_between_retries,
            exponential_backoff=exponential_backoff,
            response_model=response_model,
            parse_response=parse_response,
            structured_outputs=structured_outputs,
            use_json_mode=use_json_mode,
            save_response_to_file=save_response_to_file,
            stream=stream,
            stream_intermediate_steps=stream_intermediate_steps,
            team=team,
            team_data=team_data,
            role=role,
            respond_directly=respond_directly,
            add_transfer_instructions=add_transfer_instructions,
            team_response_separator=team_response_separator,
            debug_mode=debug_mode,
            monitoring=monitoring,
            telemetry=telemetry,
        )
