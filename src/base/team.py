from typing import List, Optional, Sequence, cast

from pydantic import BaseModel

from agno.team import Team as AgnoTeam
from agno.media import Audio, File, Image, Video
from agno.memory.v2.memory import Memory, SessionSummary
from agno.models.base import Model
from agno.models.message import Message
from agno.tools.function import Function
from agno.tools.toolkit import Toolkit
from agno.utils.log import log_warning


class Team(AgnoTeam):
    def get_members_system_message_content(self, indent: int = 0) -> str:
        system_message_content = ""
        for idx, member in enumerate(self.members):
            url_safe_member_id = self._get_member_id(member)

            if isinstance(member, Team):
                system_message_content += f"{indent * ' '} - 团队: {member.name}\n"
                system_message_content += f"{indent * ' '} - ID: {url_safe_member_id}\n"
                if member.members is not None:
                    system_message_content += member.get_members_system_message_content(
                        indent=indent + 2
                    )
            else:
                system_message_content += f"{indent * ' '} - 代理 {idx + 1}:\n"
                if member.name is not None:
                    system_message_content += (
                        f"{indent * ' '}   - ID: {url_safe_member_id}\n"
                    )
                    system_message_content += (
                        f"{indent * ' '}   - 名称: {member.name}\n"
                    )
                if member.role is not None:
                    system_message_content += (
                        f"{indent * ' '}   - 角色: {member.role}\n"
                    )
                if member.tools is not None and self.add_member_tools_to_system_message:
                    system_message_content += f"{indent * ' '}   - 成员可用工具:\n"
                    for _tool in member.tools:
                        if isinstance(_tool, Toolkit):
                            for _func in _tool.functions.values():
                                if _func.entrypoint:
                                    system_message_content += (
                                        f"{indent * ' '}    - {_func.name}\n"
                                    )
                        elif isinstance(_tool, Function) and _tool.entrypoint:
                            system_message_content += (
                                f"{indent * ' '}    - {_tool.name}\n"
                            )
                        elif callable(_tool):
                            system_message_content += (
                                f"{indent * ' '}    - {_tool.__name__}\n"
                            )

        return system_message_content

    def get_system_message(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        audio: Optional[Sequence[Audio]] = None,
        images: Optional[Sequence[Image]] = None,
        videos: Optional[Sequence[Video]] = None,
        files: Optional[Sequence[File]] = None,
    ) -> Optional[Message]:
        """Get the system message for the team."""
        # 1. Build and return the default system message for the Team.
        # 1.1 Build the list of instructions for the system message
        self.model = cast(Model, self.model)
        instructions: List[str] = []
        if self.instructions is not None:
            _instructions = self.instructions
            if callable(self.instructions):
                _instructions = self.instructions(agent=self)

            if isinstance(_instructions, str):
                instructions.append(_instructions)
            elif isinstance(_instructions, list):
                instructions.extend(_instructions)

        # 1.2 Add instructions from the Model
        _model_instructions = self.model.get_instructions_for_model()
        if _model_instructions is not None:
            instructions.extend(_model_instructions)

        # 1.3 Build a list of additional information for the system message
        additional_information: List[str] = []
        # 1.3.1 Add instructions for using markdown
        if self.markdown and self.response_model is None:
            additional_information.append("使用Markdown格式来编写你的回答。")
        # 1.3.2 Add the current datetime
        if self.add_datetime_to_instructions:
            from datetime import datetime

            additional_information.append(f"当前时间是{datetime.now()}")

        # 2 Build the default system message for the Agent.
        system_message_content: str = ""
        system_message_content += "你是一个AI智能体团队及子团队的领导者。\n"
        system_message_content += "你的任务是协调团队完成用户的请求。\n"

        system_message_content += "\n以下是团队中的成员：\n"
        system_message_content += "<team_members>\n"
        system_message_content += self.get_members_system_message_content()
        if self.get_member_information_tool:
            system_message_content += (
                "如需获取团队成员信息，可随时使用`get_member_information`工具。\n"
            )
        system_message_content += "</team_members>\n"

        system_message_content += "\n<how_to_respond>\n"
        if self.mode == "coordinate":
            system_message_content += (
                "- 您可以直接响应或将任务转移给团队中最有可能完成用户请求的成员\n"
                "- 在转移任务前请仔细分析成员可用的工具及其角色\n"
                "- 您不能直接使用成员工具，只能通过转移任务的方式\n"
                "- 转移任务时必须包含以下要素：\n"
                "  - member_id (str): 接收任务的成员ID\n"
                "  - task_description (str): 清晰的任务描述\n"
                "  - expected_output (str): 期望的输出结果\n"
                "- 可以同时向多个成员转移任务\n"
                "- 在响应用户前必须分析成员的响应结果\n"
                "- 如果认为任务已完成，请停止流程并响应用户\n"
                "- 如果对成员响应不满意，应重新分配任务\n"
            )
        elif self.mode == "route":
            system_message_content += (
                "- 您可以直接响应或将任务转发给最合适的团队成员\n"
                "- 转发前请仔细分析成员的工具和角色\n"
                "- 转发任务时必须包含：\n"
                "  - member_id (str): 接收成员的ID\n"
                "  - expected_output (str): 期望的输出结果\n"
                "- 支持同时向多个成员转发任务\n"
            )
        elif self.mode == "collaborate":
            system_message_content += (
                "- 您可以直接响应或使用`run_member_agents`工具发起团队协作\n"
                "- 协作时请确保只调用`run_member_agents`一次\n"
                "- 分析所有成员的响应并评估任务完成情况\n"
                "- 确认任务完成后请及时响应用户\n"
            )
        system_message_content += "</how_to_respond>\n\n"

        if self.enable_agentic_context:
            system_message_content += "<shared_context>\n"
            system_message_content += (
                "你可以访问一个将被所有团队成员共享的上下文空间。\n"
            )
            system_message_content += (
                "请利用这个共享上下文来提升智能体之间的沟通与协作效率。\n"
            )
            system_message_content += "请务必尽可能频繁地更新共享上下文内容。\n"
            system_message_content += (
                "要更新共享上下文，请使用 `set_shared_context` 工具。\n"
            )
            system_message_content += "</shared_context>\n\n"

        if self.name is not None:
            system_message_content += f"你的名称是：{self.name}\n\n"

        if self.success_criteria:
            system_message_content += "当满足以下标准时，表示任务成功完成：\n"
            system_message_content += "<success_criteria>\n"
            system_message_content += f"{self.success_criteria}\n"
            system_message_content += "</success_criteria>\n"
            system_message_content += "当成功标准达成时，请终止团队运行。\n\n"

        # Attached media
        if (
            audio is not None
            or images is not None
            or videos is not None
            or files is not None
        ):
            system_message_content += "<attached_media>\n"
            system_message_content += "您的消息包含以下附件类型：\n"
            if audio is not None and len(audio) > 0:
                system_message_content += " - 音频\n"
            if images is not None and len(images) > 0:
                system_message_content += " - 图片\n"
            if videos is not None and len(videos) > 0:
                system_message_content += " - 视频\n"
            if files is not None and len(files) > 0:
                system_message_content += " - 文件\n"
            system_message_content += "</attached_media>\n\n"

        # Then add memories to the system prompt
        if self.memory:
            if isinstance(self.memory, Memory) and (self.add_memory_references):
                if not user_id:
                    user_id = "default"
                user_memories = self.memory.memories.get(user_id, {})  # type: ignore
                if user_memories and len(user_memories) > 0:
                    system_message_content += "您可以访问之前与用户互动中的记忆：\n\n"
                    system_message_content += "<memories_from_previous_interactions>"
                    for _memory in user_memories.values():  # type: ignore
                        system_message_content += f"\n- {_memory.memory}"
                    system_message_content += (
                        "\n</memories_from_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：这些信息来自之前的互动，可能会在本次对话中更新。"
                        "您应始终优先使用本次对话中的信息而非历史记忆。\n\n"
                    )
                else:
                    system_message_content += (
                        "您具备保留与用户之前互动记忆的能力，"
                        "但当前尚未有任何互动记录。\n"
                    )

                if self.enable_agentic_memory:
                    system_message_content += (
                        "您可以使用`update_user_memory`记忆管理工具。\n"
                        "该工具支持新增记忆、更新现有记忆、删除特定记忆或清空所有记忆。\n"
                        "记忆应包含能够个性化用户长期互动的重要细节。\n"
                        "当识别到对话中有需要记录的新信息时，请主动使用此工具。\n"
                        "当用户明确要求更新、删除记忆或清空记忆时，必须使用此工具。\n"
                        "使用记忆工具后，请确保将操作结果反馈给用户。\n\n"
                    )

            # Then add a summary of the interaction to the system prompt
            if isinstance(self.memory, Memory) and self.add_session_summary_references:
                if not user_id:
                    user_id = "default"
                session_summary: SessionSummary = self.memory.summaries.get(user_id, {}).get(session_id, None)  # type: ignore
                if session_summary is not None:
                    system_message_content += "以下是你之前交互的简要摘要：\n\n"
                    system_message_content += "<summary_of_previous_interactions>\n"
                    system_message_content += session_summary.summary
                    system_message_content += (
                        "\n</summary_of_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "注意：这些信息来自之前的交互，可能已过时。"
                        "你应始终优先考虑本次对话中的信息，而非过去的摘要。\n\n"
                    )

        if self.description is not None:
            system_message_content += (
                f"<description>\n{self.description}\n</description>\n\n"
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
            system_message_content = self._format_message_with_state_variables(
                system_message_content, user_id=user_id
            )

        system_message_from_model = self.model.get_system_message_for_model()
        if system_message_from_model is not None:
            system_message_content += system_message_from_model

        if self.expected_output is not None:
            system_message_content += f"<expected_output>\n{self.expected_output.strip()}\n</expected_output>\n\n"

        if self.additional_context is not None:
            system_message_content += f"<additional_context>\n{self.additional_context.strip()}\n</additional_context>\n\n"

        # Add the JSON output prompt if response_model is provided and structured_outputs is False
        if (
            self.response_model is not None
            and self.use_json_mode
            and self.model
            and self.model.supports_native_structured_outputs
        ):
            system_message_content += f"{self._get_json_output_prompt()}"

        return Message(role="system", content=system_message_content.strip())

    def _get_json_output_prompt(self) -> str:
        """Return the JSON output prompt for the Agent.

        This is added to the system prompt when the response_model is set and structured_outputs is False.
        """
        import json

        json_output_prompt = "请将输出内容以JSON格式提供，并包含以下字段："
        if self.response_model is not None:
            if isinstance(self.response_model, str):
                json_output_prompt += "\n<json_fields>"
                json_output_prompt += f"\n{self.response_model}"
                json_output_prompt += "\n</json_fields>"
            elif isinstance(self.response_model, list):
                json_output_prompt += "\n<json_fields>"
                json_output_prompt += f"\n{json.dumps(obj=self.response_model, ensure_ascii=False, indent=2)}"
                json_output_prompt += "\n</json_fields>"
            elif issubclass(self.response_model, BaseModel):
                json_schema = self.response_model.model_json_schema()
                if json_schema is not None:
                    response_model_properties = {}
                    json_schema_properties = json_schema.get("properties")
                    if json_schema_properties is not None:
                        for (
                            field_name,
                            field_properties,
                        ) in json_schema_properties.items():
                            formatted_field_properties = {
                                prop_name: prop_value
                                for prop_name, prop_value in field_properties.items()
                                if prop_name != "title"
                            }
                            response_model_properties[field_name] = (
                                formatted_field_properties
                            )
                    json_schema_defs = json_schema.get("$defs")
                    if json_schema_defs is not None:
                        response_model_properties["$defs"] = {}
                        for def_name, def_properties in json_schema_defs.items():
                            def_fields = def_properties.get("properties")
                            formatted_def_properties = {}
                            if def_fields is not None:
                                for field_name, field_properties in def_fields.items():
                                    formatted_field_properties = {
                                        prop_name: prop_value
                                        for prop_name, prop_value in field_properties.items()
                                        if prop_name != "title"
                                    }
                                    formatted_def_properties[field_name] = (
                                        formatted_field_properties
                                    )
                            if len(formatted_def_properties) > 0:
                                response_model_properties["$defs"][
                                    def_name
                                ] = formatted_def_properties

                    if len(response_model_properties) > 0:
                        json_output_prompt += "\n<json_fields>"
                        json_output_prompt += f"\n{json.dumps(obj=[key for key in response_model_properties.keys() if key != '$defs'], ensure_ascii=False, indent=2)}"
                        json_output_prompt += "\n</json_fields>"
                        json_output_prompt += "\n\n以下是每个字段的属性说明："
                        json_output_prompt += "\n<json_field_properties>"
                        json_output_prompt += f"\n{json.dumps(obj=response_model_properties, ensure_ascii=False, indent=2)}"
                        json_output_prompt += "\n</json_field_properties>"
            else:
                log_warning(f"Could not build json schema for {self.response_model}")
        else:
            json_output_prompt += "请以JSON格式提供输出。"

        json_output_prompt += "\n请以 `{` 开始响应，并以 `}` 结束。"
        json_output_prompt += "\n你的输出将被传递给json.loads()来转换为Python对象。"
        json_output_prompt += "\n请确保只包含有效的JSON内容。"
        return json_output_prompt
