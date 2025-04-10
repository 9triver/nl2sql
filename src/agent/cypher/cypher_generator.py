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

from pydantic import BaseModel
from agno.agent import Agent
from agno.models.base import Model
from agno.models.message import Message
from agno.memory.agent import AgentMemory
from agno.knowledge.agent import AgentKnowledge
from agno.storage.base import Storage
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from tools.cypher_knowledge import CypherKnowledge
from tools.neq4j import Neo4jTools
from agno.tools.duckduckgo import DuckDuckGoTools
from param import Parameter
from loguru import logger


class CypherGeneratorAgent(Agent):
    role = dedent(
        """Generate precise and efficient Cypher statements based on user's natural language requirements. Please provide specific and useful infomation."""
    )
    description = None
    instructions = dedent(
        """\
        - Follow and Print the **Thought-Retrive-Generation** chain-of-thought traces:
            1. **Thought**: Reasoning based on the user question and previous generation.
            2. **Act**: Use one tool.
            3. **Generation**: Analyse the result of previous act, And Generate a Cypher statement(may be incomplete).
        - Print And Answer in Chinese. But don't translate the infomation in database.
        - Continue the **Thought-Act-Observation** loop until:
            1. You are confident that you generate a syntactically correct Cypher statement which can anwser user question.
            2. Or You think the user should provide more infomation.
        
        Language Infomation:
        - The cypher cheatsheet is texts in English, so please search in English.
        - The user's question and the data in the neo4j database are Chinese text.\
    """
    )

    def __init__(
        self,
        param: Parameter,
        *,
        model: Optional[Model] = None,
        name: Optional[str] = "Cypher Generator",
        agent_id: Optional[str] = None,
        introduction: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
        session_state: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        add_context: bool = False,
        resolve_context: bool = True,
        memory: Optional[AgentMemory] = None,
        add_history_to_messages: bool = False,
        num_history_responses: int = 3,
        knowledge: Optional[AgentKnowledge] = None,
        add_references: bool = False,
        retriever: Optional[Callable[..., Optional[List[Dict]]]] = None,
        references_format: Literal["json", "yaml"] = "json",
        storage: Optional[Storage] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Union[Toolkit, Callable, Function, Dict]]] = None,
        show_tool_calls: bool = True,
        tool_call_limit: Optional[int] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        reasoning: bool = False,
        reasoning_model: Optional[Model] = None,
        reasoning_agent: Optional[Agent] = None,
        reasoning_min_steps: int = 1,
        reasoning_max_steps: int = 10,
        read_chat_history: bool = False,
        search_knowledge: bool = True,
        update_knowledge: bool = False,
        read_tool_call_history: bool = False,
        system_message: Optional[Union[str, Callable, Message]] = None,
        system_message_role: str = "system",
        create_default_system_message: bool = True,
        description: Optional[str] = description,
        goal: Optional[str] = None,
        instructions: Optional[Union[str, List[str], Callable]] = instructions,
        expected_output: Optional[str] = None,
        additional_context: Optional[str] = None,
        markdown: bool = True,
        add_name_to_instructions: bool = False,
        add_datetime_to_instructions: bool = False,
        add_state_in_messages: bool = False,
        add_messages: Optional[List[Union[Dict, Message]]] = None,
        user_message: Optional[Union[List, Dict, str, Callable, Message]] = None,
        user_message_role: str = "user",
        create_default_user_message: bool = True,
        retries: int = 0,
        delay_between_retries: int = 1,
        exponential_backoff: bool = False,
        response_model: Optional[Type[BaseModel]] = None,
        parse_response: bool = True,
        structured_outputs: bool = False,
        save_response_to_file: Optional[str] = None,
        stream: Optional[bool] = True,
        stream_intermediate_steps: bool = True,
        team: Optional[List[Agent]] = None,
        team_data: Optional[Dict[str, Any]] = None,
        role: Optional[str] = role,
        respond_directly: bool = False,
        add_transfer_instructions: bool = True,
        team_response_separator: str = "\n",
        debug_mode: bool = False,
        monitoring: bool = False,
        telemetry: bool = True,
    ):
        if tools is None:
            tools = [
                CypherKnowledge(),
                DuckDuckGoTools(news=False),
                Neo4jTools(
                    user=param.DATABASE_USER,
                    password=param.DATABASE_PASSWORD,
                    db_uri=param.DATABASE_URL,
                    database=param.DATABASE_NAME,
                ).check_cypher_syntax,
            ]
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
            add_history_to_messages=add_history_to_messages,
            num_history_responses=num_history_responses,
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
