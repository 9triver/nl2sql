from agno.agent import Agent as AgnoAgent

from typing import List, Optional

from agno.memory.agent import AgentMemory
from agno.memory.v2.memory import Memory, SessionSummary
from agno.models.message import Message
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from agno.utils.log import log_warning
from .prompts import get_json_output_prompt


class Agent(AgnoAgent):
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

            # Add the JSON output prompt if response_model is provided and structured_outputs is False
            if (
                self.response_model is not None
                and self.model
                and (
                    self.model.supports_native_structured_outputs
                    and (self.use_json_mode or self.structured_outputs is False)
                )
            ):
                sys_message_content += f"\n{get_json_output_prompt(self.response_model)}"  # type: ignore

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
        _model_instructions = self.model.get_instructions_for_model()
        if _model_instructions is not None:
            instructions.extend(_model_instructions)

        # 3.2 Build a list of additional information for the system message
        additional_information: List[str] = []
        # 3.2.1 Add instructions for using markdown
        if self.markdown and self.response_model is None:
            additional_information.append("Use markdown to format your answers.")
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

            additional_information.append(f"The current time is {time}.")
        # 3.2.3 Add agent name if provided
        if self.name is not None and self.add_name_to_instructions:
            additional_information.append(f"Your name is: {self.name}.")

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
                "您是一个AI智能体团队的负责人：\n"
                "- 您可以直接响应请求，或根据工具可用性将任务转交给团队中的其他智能体\n"
                "- 转交任务时必须包含以下要素：\n"
                "  - task_description (str): 清晰的任务描述\n"
                "  - expected_output (str): 期望的输出结果\n"
                "  - additional_information (str): 辅助任务完成的补充信息\n"
                "- 在响应用户前必须始终验证其他智能体的输出\n"
                "- 若对结果不满意，可以重新指派该任务\n"
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
                    system_message_content += "您可以访问以下与用户之前的交互记忆：\n\n"
                    system_message_content += "<memories_from_previous_interactions>"
                    for _memory in self.memory.memories:
                        system_message_content += f"\n- {_memory.memory}"
                    system_message_content += (
                        "\n</memories_from_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：这些记忆来自历史交互，可能在当前对话中被更新。"
                        "您应始终优先使用本次对话中的最新信息而非历史记忆。\n\n"
                    )
                else:
                    system_message_content += (
                        "您具备记忆存储功能，但目前尚未与用户建立过交互记录。\n"
                    )
                system_message_content += (
                    "您可以通过`update_memory`工具更新记忆。\n"
                    "使用`update_memory`工具后，请确保将响应结果返回给用户。\n\n"
                )
            elif isinstance(self.memory, Memory) and (self.add_memory_references):
                if not user_id:
                    user_id = "default"
                user_memories = self.memory.get_user_memories(user_id=user_id)  # type: ignore
                if user_memories and len(user_memories) > 0:
                    system_message_content += "您可以访问以下与用户之前互动的记忆：\n\n"
                    system_message_content += "<memories_from_previous_interactions>"
                    for _memory in user_memories:  # type: ignore
                        system_message_content += f"\n- {_memory.memory}"
                    system_message_content += (
                        "\n</memories_from_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：这些信息来自之前的互动，可能会在本次对话中更新。"
                        "您应始终优先使用本次对话中的最新信息而非历史记忆。\n"
                    )
                else:
                    system_message_content += (
                        "您具备保留用户互动记忆的能力，但当前尚未建立任何互动记录。\n"
                    )

                if self.enable_agentic_memory:
                    system_message_content += (
                        "\n<updating_user_memories>\n"
                        "- 您可以使用`update_user_memory`工具来新增、修改、删除或清空记忆\n"
                        "- 当用户提供需要长期记忆的信息时，请使用该工具更新记忆数据库\n"
                        "- 记忆应包含有助于个性化用户交互的重要细节\n"
                        "- 在识别到对话中有需要记录的信息时，请主动使用该工具\n"
                        "- 当用户明确要求操作记忆时（如更新/删除/清空），请使用该工具\n"
                        "- 使用记忆工具后，请务必将操作结果反馈给用户\n"
                        "</updating_user_memories>\n\n"
                    )

            # 3.3.11 Then add a summary of the interaction to the system prompt
            if (
                isinstance(self.memory, AgentMemory)
                and self.memory.create_session_summary
            ):
                if self.memory.summary is not None:
                    system_message_content += "以下是你之前交互记录的简要摘要：\n\n"
                    system_message_content += "<历史交互摘要>\n"
                    system_message_content += str(self.memory.summary)
                    system_message_content += "\n</历史交互摘要>\n\n"
                    system_message_content += (
                        "请注意：这些信息来自历史交互记录，可能已过时。"
                        "你应当始终优先采用本次对话中的最新信息。\n\n"
                    )
            elif (
                isinstance(self.memory, Memory) and self.add_session_summary_references
            ):
                if not user_id:
                    user_id = "default"
                session_summary: SessionSummary = self.memory.summaries.get(user_id, {}).get(session_id, None)  # type: ignore
                if session_summary is not None:
                    system_message_content += "以下是你之前交互记录的简要摘要：\n\n"
                    system_message_content += "<summary_of_previous_interactions>\n"
                    system_message_content += session_summary.summary
                    system_message_content += (
                        "\n</summary_of_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：这些信息来自历史交互记录，可能已过时。"
                        "你应当始终优先采纳本次对话中的最新信息。\n\n"
                    )

        # 3.3.12 Finally, add the system message from the Model
        system_message_from_model = self.model.get_system_message_for_model()
        if system_message_from_model is not None:
            system_message_content += system_message_from_model

        # Add the JSON output prompt if response_model is provided and structured_outputs is False (only applicable if the model supports structured outputs)
        if self.response_model is not None and not (
            self.model.supports_native_structured_outputs
            and (not self.use_json_mode or self.structured_outputs is True)
        ):
            system_message_content += f"{get_json_output_prompt(self.response_model)}"  # type: ignore

        # Return the system message
        return (
            Message(role=self.system_message_role, content=system_message_content.strip())  # type: ignore
            if system_message_content
            else None
        )

    def get_transfer_instructions(self) -> str:
        if self.team and len(self.team) > 0:
            transfer_instructions = "你可以将任务转交给以下团队成员：\n"
            for agent_index, agent in enumerate(self.team):
                transfer_instructions += f"\n成员：{agent_index + 1}：\n"
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
