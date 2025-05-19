from textwrap import dedent
from typing import Any, List, Optional, Sequence, Union, cast

from agno.agent import Agent as AgnoAgent
from agno.media import Audio, File, Image, Video
from agno.memory.agent import AgentMemory
from agno.memory.v2.memory import Memory, SessionSummary
from agno.models.message import Message, MessageReferences
from agno.run.response import RunResponse, RunResponseExtraData
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from agno.utils.log import log_debug, log_warning
from agno.utils.timer import Timer

from .prompts import get_json_output_prompt


class Agent(AgnoAgent):
    def get_transfer_instructions(self) -> str:
        if self.team and len(self.team) > 0:
            transfer_instructions = "你可以将任务转交给以下团队成员：\n"
            for agent_index, agent in enumerate(self.team):
                transfer_instructions += f"\n成员：{agent_index + 1}:\n"
                if agent.name:
                    transfer_instructions += f"名称：{agent.name}\n"
                if agent.role:
                    transfer_instructions += f"角色：{agent.role}\n"
                if agent.tools is not None:
                    _tools = []
                    for _tool in agent.tools:
                        if isinstance(_tool, Toolkit):
                            _tools.extend(list(_tool.functions.keys()))
                        elif isinstance(_tool, Function):
                            _tools.append(_tool.name)
                        elif callable(_tool):
                            _tools.append(_tool.__name__)
                    transfer_instructions += f"可用工具：{', '.join(_tools)}\n"
            return transfer_instructions
        return ""

    def get_system_message(
        self, session_id: str, user_id: Optional[str] = None
    ) -> Optional[Message]:
        """Return the system message for the Agent.

        1. If the system_message is provided, use that.
        2. If create_default_system_message is False, return None.
        3. Build and return the default system message for the Agent.
        """

        # 1. If the system_message is provided, use that.
        if self.system_message is not None:
            if isinstance(self.system_message, Message):
                return self.system_message

            sys_message_content: str = ""
            if isinstance(self.system_message, str):
                sys_message_content = self.system_message
            elif callable(self.system_message):
                sys_message_content = self.system_message(agent=self)
                if not isinstance(sys_message_content, str):
                    raise Exception("system_message must return a string")

            # Format the system message with the session state variables
            if self.add_state_in_messages:
                sys_message_content = self.format_message_with_state_variables(
                    sys_message_content
                )

            # Add the JSON output prompt if response_model is provided and the model does not support native structured outputs or JSON schema outputs
            # or if use_json_mode is True
            if (
                self.model is not None
                and self.response_model is not None
                and not (
                    (
                        self.model.supports_native_structured_outputs
                        or self.model.supports_json_schema_outputs
                    )
                    and (not self.use_json_mode or self.structured_outputs is True)
                )
            ):
                sys_message_content += (
                    f"\n{get_json_output_prompt(self.response_model)}"  # type: ignore
                )

            # type: ignore
            return Message(role=self.system_message_role, content=sys_message_content)

        # 2. If create_default_system_message is False, return None.
        if not self.create_default_system_message:
            return None

        if self.model is None:
            raise Exception("model not set")

        # 3. Build and return the default system message for the Agent.
        # 3.1 Build the list of instructions for the system message
        instructions: List[str] = []
        if self.instructions is not None:
            _instructions = self.instructions
            if callable(self.instructions):
                _instructions = self.instructions(agent=self)

            if isinstance(_instructions, str):
                instructions.append(_instructions)
            elif isinstance(_instructions, list):
                instructions.extend(_instructions)
        # 3.1.1 Add instructions from the Model
        _model_instructions = self.model.get_instructions_for_model(
            self._tools_for_model
        )
        if _model_instructions is not None:
            instructions.extend(_model_instructions)

        # 3.2 Build a list of additional information for the system message
        additional_information: List[str] = []
        # 3.2.1 Add instructions for using markdown
        if self.markdown and self.response_model is None:
            additional_information.append("使用Markdown格式来回答。")
        # 3.2.2 Add the current datetime
        if self.add_datetime_to_instructions:
            from datetime import datetime

            tz = None

            if self.timezone_identifier:
                try:
                    from zoneinfo import ZoneInfo

                    tz = ZoneInfo(self.timezone_identifier)
                except Exception:
                    log_warning("Invalid timezone identifier")

            time = datetime.now(tz) if tz else datetime.now()

            additional_information.append(f"当前时间是 {time}。")
        # 3.2.3 Add agent name if provided
        if self.name is not None and self.add_name_to_instructions:
            additional_information.append(f"你的名字是: {self.name}。")

        # 3.2.4 Add information about agentic filters if enabled
        if self.knowledge is not None and self.enable_agentic_knowledge_filters:
            valid_filters = getattr(self.knowledge, "valid_metadata_filters", None)
            if valid_filters:
                valid_filters_str = ", ".join(valid_filters)
                additional_information.append(
                    dedent(f"""
                    知识库中包含以下元数据筛选条件的文档: {valid_filters_str}。
                    当用户查询包含特定元数据时，必须使用筛选条件。

                    示例：
                    1. 如果用户查询特定人员如"乔丹·米切尔"，你必须使用search_knowledge_base工具，并将filters参数设置为{{'<有效键如user_id>': '<基于用户查询的有效值>'}}。
                    2. 如果用户查询特定文档类型如"合同"，你必须使用search_knowledge_base工具，并将filters参数设置为{{'document_type': 'contract'}}。
                    3. 如果用户查询特定地点如"来自纽约的文档"，你必须使用search_knowledge_base工具，并将filters参数设置为{{'<有效键如location>': '纽约'}}。

                    通用准则：
                    - 始终分析用户查询以识别相关元数据
                    - 使用尽可能具体的筛选条件来缩小结果范围
                    - 如果多个筛选条件相关，请在filters参数中组合使用(例如{{'name': '乔丹·米切尔', 'document_type': 'contract'}})
                    - 确保筛选键与有效元数据筛选条件匹配: {valid_filters_str}

                    你可以使用search_knowledge_base工具搜索知识库并获取最相关的文档。确保将filters作为[Dict[str: Any]]传递给该工具。严格遵守此结构。
                """)
                )

        # 3.3 Build the default system message for the Agent.
        system_message_content: str = ""
        # 3.3.1 First add the Agent description if provided
        if self.description is not None:
            system_message_content += f"{self.description}\n"
        # 3.3.2 Then add the Agent goal if provided
        if self.goal is not None:
            system_message_content += f"\n<your_goal>\n{self.goal}\n</your_goal>\n\n"
        # 3.3.3 Then add the Agent role if provided
        if self.role is not None:
            system_message_content += f"\n<your_role>\n{self.role}\n</your_role>\n\n"
        # 3.3.4 Then add instructions for transferring tasks to team members
        if self.has_team and self.add_transfer_instructions:
            system_message_content += (
                "<agent_team>\n"
                "你是AI智能体团队的领导者:\n"
                "- 你可以直接响应或根据其他智能体可用的工具将任务转交给他们\n"
                "- 如果将任务转交给其他智能体，请确保包含:\n"
                "  - task_description (str): 清晰的任务描述\n"
                "  - expected_output (str): 期望的输出结果\n"
                "  - additional_information (str): 有助于智能体完成任务的其他信息\n"
                "- 在向用户响应前，你必须验证其他智能体的输出\n"
                "- 如果对结果不满意，你可以重新分配该任务\n"
                "</agent_team>\n\n"
            )
        # 3.3.5 Then add instructions for the Agent
        if len(instructions) > 0:
            system_message_content += "<instructions>"
            if len(instructions) > 1:
                for _upi in instructions:
                    system_message_content += f"\n- {_upi}"
            else:
                system_message_content += "\n" + instructions[0]
            system_message_content += "\n</instructions>\n\n"
        # 3.3.6 Add additional information
        if len(additional_information) > 0:
            system_message_content += "<additional_information>"
            for _ai in additional_information:
                system_message_content += f"\n- {_ai}"
            system_message_content += "\n</additional_information>\n\n"
        # 3.3.7 Then add instructions for the tools
        if self._tool_instructions is not None:
            for _ti in self._tool_instructions:
                system_message_content += f"{_ti}\n"

        # Format the system message with the session state variables
        if self.add_state_in_messages:
            system_message_content = self.format_message_with_state_variables(
                system_message_content
            )

        # 3.3.7 Then add the expected output
        if self.expected_output is not None:
            system_message_content += f"<expected_output>\n{self.expected_output.strip()}\n</expected_output>\n\n"
        # 3.3.8 Then add additional context
        if self.additional_context is not None:
            system_message_content += f"{self.additional_context}\n"
        # 3.3.9 Then add information about the team members
        if self.has_team and self.add_transfer_instructions:
            system_message_content += f"<transfer_instructions>\n{self.get_transfer_instructions().strip()}\n</transfer_instructions>\n\n"
        # 3.3.10 Then add memories to the system prompt
        if self.memory:
            if (
                isinstance(self.memory, AgentMemory)
                and self.memory.create_user_memories
            ):
                if self.memory.memories and len(self.memory.memories) > 0:
                    system_message_content += (
                        "你可以访问之前与用户互动的记忆，这些记忆可供你使用：\n\n"
                    )
                    system_message_content += "<memories_from_previous_interactions>"
                    for _memory in self.memory.memories:
                        system_message_content += f"\n- {_memory.memory}"
                    system_message_content += (
                        "\n</memories_from_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：此信息来自之前的交互，可能会在本次对话中更新。"
                        "你应该始终优先考虑本次对话中的信息而非过去的记忆。\n\n"
                    )
                else:
                    system_message_content += (
                        "你具备保留与用户之前互动记忆的能力，"
                        "但尚未与用户有过任何互动。\n"
                    )
                system_message_content += (
                    "你可以使用`update_memory`工具添加新的记忆。\n"
                    "如果使用`update_memory`工具，请记得将响应传递给用户。\n\n"
                )
            elif isinstance(self.memory, Memory) and self.add_memory_references:
                if not user_id:
                    user_id = "default"
                user_memories = self.memory.get_user_memories(user_id=user_id)  # type: ignore
                if user_memories and len(user_memories) > 0:
                    system_message_content += (
                        "你可以访问之前与用户互动的记忆，这些记忆可供你使用：\n\n"
                    )
                    system_message_content += "<memories_from_previous_interactions>"
                    for _memory in user_memories:  # type: ignore
                        system_message_content += f"\n- {_memory.memory}"
                    system_message_content += (
                        "\n</memories_from_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：此信息来自之前的交互记录，可能会在本次对话中更新。"
                        "你应该始终优先采用本次对话中的信息而非过去的记忆。\n"
                    )
                else:
                    system_message_content += (
                        "你具备保留与用户之前交互记忆的能力，"
                        "但尚未与用户有过任何交互。\n"
                    )

                if self.enable_agentic_memory:
                    system_message_content += (
                        "\n<updating_user_memories>\n"
                        "- 你可以使用`update_user_memory`工具来添加新记忆、更新现有记忆、删除记忆或清除所有记忆\n"
                        "- 如果用户的消息包含应该被记录为记忆的信息，请使用`update_user_memory`工具更新你的记忆数据库\n"
                        "- 记忆应包含可以个性化与用户持续互动的细节\n"
                        "- 使用此工具添加新记忆或更新你在对话中识别出的现有记忆\n"
                        "- 当用户要求更新记忆、删除记忆或清除所有记忆时使用此工具\n"
                        "- 如果你使用了`update_user_memory`工具，记得将响应传递给用户\n"
                        "</updating_user_memories>\n\n"
                    )

            # 3.3.11 Then add a summary of the interaction to the system prompt
            if (
                isinstance(self.memory, AgentMemory)
                and self.memory.create_session_summary
            ):
                if self.memory.summary is not None:
                    system_message_content += "以下是你之前交互的简要总结：\n\n"
                    system_message_content += "<summary_of_previous_interactions>\n"
                    system_message_content += str(self.memory.summary)
                    system_message_content += (
                        "\n</summary_of_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：这些信息来自之前的交互可能已过时。"
                        "你应始终优先使用当前对话中的信息而非历史总结。\n\n"
                    )
            elif (
                isinstance(self.memory, Memory) and self.add_session_summary_references
            ):
                if not user_id:
                    user_id = "default"
                session_summary: SessionSummary = self.memory.summaries.get(
                    user_id, {}
                ).get(session_id, None)  # type: ignore
                if session_summary is not None:
                    system_message_content += "以下是您之前交互的简要摘要：\n\n"
                    system_message_content += "<summary_of_previous_interactions>\n"
                    system_message_content += session_summary.summary
                    system_message_content += (
                        "\n</summary_of_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：此信息来自之前的交互，可能已过时。"
                        "您应始终优先使用当前对话中的信息而非过去的摘要。\n\n"
                    )

        # 3.3.12 Add the system message from the Model
        system_message_from_model = self.model.get_system_message_for_model(
            self._tools_for_model
        )
        if system_message_from_model is not None:
            system_message_content += system_message_from_model

        # 3.3.13 Add the JSON output prompt if response_model is provided and the model does not support native structured outputs or JSON schema outputs
        # or if use_json_mode is True
        if self.response_model is not None and not (
            (
                self.model.supports_native_structured_outputs
                or self.model.supports_json_schema_outputs
            )
            and (not self.use_json_mode or self.structured_outputs is True)
        ):
            system_message_content += f"{get_json_output_prompt(self.response_model)}"  # type: ignore

        # Return the system message
        return (
            Message(
                role=self.system_message_role, content=system_message_content.strip()
            )  # type: ignore
            if system_message_content
            else None
        )

    def get_user_message(
        self,
        *,
        message: Optional[Union[str, List]],
        audio: Optional[Sequence[Audio]] = None,
        images: Optional[Sequence[Image]] = None,
        videos: Optional[Sequence[Video]] = None,
        files: Optional[Sequence[File]] = None,
        **kwargs: Any,
    ) -> Optional[Message]:
        """Return the user message for the Agent.

        1. If the user_message is provided, use that.
        2. If create_default_user_message is False or if the message is a list, return the message as is.
        3. Build the default user message for the Agent
        """
        # Get references from the knowledge base to use in the user message
        references = None
        self.run_response = cast(RunResponse, self.run_response)
        if self.add_references and message:
            message_str: str
            if isinstance(message, str):
                message_str = message
            elif callable(message):
                message_str = message(agent=self)
            else:
                raise Exception(
                    "message must be a string or a callable when add_references is True"
                )

            retrieval_timer = Timer()
            retrieval_timer.start()
            docs_from_knowledge = self.get_relevant_docs_from_knowledge(
                query=message_str, **kwargs
            )
            if docs_from_knowledge is not None:
                references = MessageReferences(
                    query=message_str,
                    references=docs_from_knowledge,
                    time=round(retrieval_timer.elapsed, 4),
                )
                # Add the references to the run_response
                if self.run_response.extra_data is None:
                    self.run_response.extra_data = RunResponseExtraData()
                if self.run_response.extra_data.references is None:
                    self.run_response.extra_data.references = []
                self.run_response.extra_data.references.append(references)
            retrieval_timer.stop()
            log_debug(f"Time to get references: {retrieval_timer.elapsed:.4f}s")

        # 1. If the user_message is provided, use that.
        if self.user_message is not None:
            if isinstance(self.user_message, Message):
                return self.user_message

            user_message_content = self.user_message
            if callable(self.user_message):
                user_message_kwargs = {
                    "agent": self,
                    "message": message,
                    "references": references,
                }
                user_message_content = self.user_message(**user_message_kwargs)
                if not isinstance(user_message_content, str):
                    raise Exception("user_message must return a string")

            if self.add_state_in_messages:
                user_message_content = self.format_message_with_state_variables(
                    user_message_content
                )

            return Message(
                role=self.user_message_role,
                content=user_message_content,
                audio=audio,
                images=images,
                videos=videos,
                files=files,
                **kwargs,
            )

        # 2. If create_default_user_message is False or message is a list, return the message as is.
        if not self.create_default_user_message or isinstance(message, list):
            return Message(
                role=self.user_message_role,
                content=message,
                images=images,
                audio=audio,
                videos=videos,
                files=files,
                **kwargs,
            )

        # 3. Build the default user message for the Agent
        # If the message is None, return None
        if message is None:
            return None

        user_msg_content = message
        # Format the message with the session state variables
        if self.add_state_in_messages:
            user_msg_content = self.format_message_with_state_variables(message)
        # 4.1 Add references to user message
        if (
            self.add_references
            and references is not None
            and references.references is not None
            and len(references.references) > 0
        ):
            user_msg_content += "\n\n如果对您有帮助，请参考以下知识库中的内容：\n"
            user_msg_content += "<references>\n"
            user_msg_content += (
                self.convert_documents_to_string(references.references) + "\n"
            )
            user_msg_content += "</references>"
        # 4.2 Add context to user message
        if self.add_context and self.context is not None:
            user_msg_content += "\n\n<context>\n"
            user_msg_content += self.convert_context_to_string(self.context) + "\n"
            user_msg_content += "</context>"

        # Return the user message
        return Message(
            role=self.user_message_role,
            content=user_msg_content,
            audio=audio,
            images=images,
            videos=videos,
            files=files,
            **kwargs,
        )
