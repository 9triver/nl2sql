from agno.team import Team as AgnoTeam

from typing import (
    Dict,
    List,
    Optional,
    Sequence,
    Union,
    cast,
)

from pydantic import BaseModel

from agno.media import Audio, File, Image, Video
from agno.memory.v2.memory import Memory, SessionSummary
from agno.models.base import Model
from agno.models.message import Message
from agno.utils.log import log_warning


class Team(AgnoTeam):
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
            additional_information.append("Use markdown to format your answers.")
        # 1.3.2 Add the current datetime
        if self.add_datetime_to_instructions:
            from datetime import datetime

            additional_information.append(f"The current time is {datetime.now()}")

        # 2 Build the default system message for the Agent.
        system_message_content: str = ""
        system_message_content += (
            "You are the leader of a team and sub-teams of AI Agents.\n"
        )
        system_message_content += (
            "Your task is to coordinate the team to complete the user's request.\n"
        )

        system_message_content += "\nHere are the members in your team:\n"
        system_message_content += "<team_members>\n"
        system_message_content += self.get_members_system_message_content()
        if self.get_member_information_tool:
            system_message_content += "If you need to get information about your team members, you can use the `get_member_information` tool at any time.\n"
        system_message_content += "</team_members>\n"

        system_message_content += "\n<how_to_respond>\n"
        if self.mode == "coordinate":
            system_message_content += (
                "- You can either respond directly or transfer tasks to members in your team with the highest likelihood of completing the user's request.\n"
                "- Carefully analyze the tools available to the members and their roles before transferring tasks.\n"
                "- You cannot use a member tool directly. You can only transfer tasks to members.\n"
                "- When you transfer a task to another member, make sure to include:\n"
                "  - member_id (str): The ID of the member to forward the task to.\n"
                "  - task_description (str): A clear description of the task.\n"
                "  - expected_output (str): The expected output.\n"
                "- You can transfer tasks to multiple members at once.\n"
                "- You must always analyze the responses from members before responding to the user.\n"
                "- After analyzing the responses from the members, if you feel the task has been completed, you can stop and respond to the user.\n"
                "- If you are not satisfied with the responses from the members, you should re-assign the task.\n"
            )
        elif self.mode == "route":
            system_message_content += (
                "- You can either respond directly or forward tasks to members in your team with the highest likelihood of completing the user's request.\n"
                "- Carefully analyze the tools available to the members and their roles before forwarding tasks.\n"
                "- When you forward a task to another Agent, make sure to include:\n"
                "  - member_id (str): The ID of the member to forward the task to.\n"
                "  - expected_output (str): The expected output.\n"
                "- You can forward tasks to multiple members at once.\n"
            )
        elif self.mode == "collaborate":
            system_message_content += (
                "- You can either respond directly or use the `run_member_agents` tool to run all members in your team to get a collaborative response.\n"
                "- To run the members in your team, call `run_member_agents` ONLY once. This will run all members in your team.\n"
                "- Analyze the responses from all members and evaluate whether the task has been completed.\n"
                "- If you feel the task has been completed, you can stop and respond to the user.\n"
            )
        system_message_content += "</how_to_respond>\n\n"

        if self.enable_agentic_context:
            system_message_content += "<shared_context>\n"
            system_message_content += "You have access to a shared context that will be shared with all members of the team.\n"
            system_message_content += "Use this shared context to improve inter-agent communication and coordination.\n"
            system_message_content += "It is important that you update the shared context as often as possible.\n"
            system_message_content += (
                "To update the shared context, use the `set_shared_context` tool.\n"
            )
            system_message_content += "</shared_context>\n\n"

        if self.name is not None:
            system_message_content += f"Your name is: {self.name}\n\n"

        if self.success_criteria:
            system_message_content += (
                "Your task is successful when the following criteria is met:\n"
            )
            system_message_content += "<success_criteria>\n"
            system_message_content += f"{self.success_criteria}\n"
            system_message_content += "</success_criteria>\n"
            system_message_content += (
                "Stop the team run when the success_criteria is met.\n\n"
            )

        # Attached media
        if (
            audio is not None
            or images is not None
            or videos is not None
            or files is not None
        ):
            system_message_content += "<attached_media>\n"
            system_message_content += (
                "You have the following media attached to your message:\n"
            )
            if audio is not None and len(audio) > 0:
                system_message_content += " - Audio\n"
            if images is not None and len(images) > 0:
                system_message_content += " - Images\n"
            if videos is not None and len(videos) > 0:
                system_message_content += " - Videos\n"
            if files is not None and len(files) > 0:
                system_message_content += " - Files\n"
            system_message_content += "</attached_media>\n\n"

        # Then add memories to the system prompt
        if self.memory:
            if isinstance(self.memory, Memory) and (self.add_memory_references):
                if not user_id:
                    user_id = "default"
                user_memories = self.memory.memories.get(user_id, {})  # type: ignore
                if user_memories and len(user_memories) > 0:
                    system_message_content += "You have access to memories from previous interactions with the user that you can use:\n\n"
                    system_message_content += "<memories_from_previous_interactions>"
                    for _memory in user_memories.values():  # type: ignore
                        system_message_content += f"\n- {_memory.memory}"
                    system_message_content += (
                        "\n</memories_from_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "Note: this information is from previous interactions and may be updated in this conversation. "
                        "You should always prefer information from this conversation over the past memories.\n\n"
                    )
                else:
                    system_message_content += (
                        "You have the capability to retain memories from previous interactions with the user, "
                        "but have not had any interactions with the user yet.\n"
                    )

                if self.enable_agentic_memory:
                    system_message_content += (
                        "You have access to the `update_user_memory` tool.\n"
                        "You can use the `update_user_memory` tool to add new memories, update existing memories, delete memories, or clear all memories.\n"
                        "Memories should include details that could personalize ongoing interactions with the user.\n"
                        "Use this tool to add new memories or update existing memories that you identify in the conversation.\n"
                        "Use this tool if the user asks to update their memory, delete a memory, or clear all memories.\n"
                        "If you use the `update_user_memory` tool, remember to pass on the response to the user.\n\n"
                    )

            # Then add a summary of the interaction to the system prompt
            if isinstance(self.memory, Memory) and self.add_session_summary_references:
                if not user_id:
                    user_id = "default"
                session_summary: SessionSummary = self.memory.summaries.get(user_id, {}).get(session_id, None)  # type: ignore
                if session_summary is not None:
                    system_message_content += (
                        "Here is a brief summary of your previous interactions:\n\n"
                    )
                    system_message_content += "<summary_of_previous_interactions>\n"
                    system_message_content += session_summary.summary
                    system_message_content += (
                        "\n</summary_of_previous_interactions>\n\n"
                    )
                    system_message_content += (
                        "Note: this information is from previous interactions and may be outdated. "
                        "You should ALWAYS prefer information from this conversation over the past summary.\n\n"
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

    def _get_user_message(
        self,
        message: Union[str, List, Dict, Message],
        audio: Optional[Sequence[Audio]] = None,
        images: Optional[Sequence[Image]] = None,
        videos: Optional[Sequence[Video]] = None,
        files: Optional[Sequence[File]] = None,
        **kwargs,
    ):
        # Build user message if message is None, str or list
        user_message_content: str = ""
        if isinstance(message, str) or isinstance(message, list):
            if self.add_state_in_messages:
                if isinstance(message, str):
                    user_message_content = self._format_message_with_state_variables(
                        message
                    )
                elif isinstance(message, list):
                    user_message_content = "\n".join(
                        [
                            self._format_message_with_state_variables(msg)
                            for msg in message
                        ]
                    )
            else:
                if isinstance(message, str):
                    user_message_content = message
                else:
                    user_message_content = "\n".join(message)

            # Add context to user message
            if self.add_context and self.context is not None:
                user_message_content += "\n\n<context>\n"
                user_message_content += (
                    self._convert_context_to_string(self.context) + "\n"
                )
                user_message_content += "</context>"

            return Message(
                role="user",
                content=user_message_content,
                audio=audio,
                images=images,
                videos=videos,
                files=files,
                **kwargs,
            )

        # 3.2 If message is provided as a Message, use it directly
        elif isinstance(message, Message):
            return message
        # 3.3 If message is provided as a dict, try to validate it as a Message
        elif isinstance(message, dict):
            try:
                return Message.model_validate(message)
            except Exception as e:
                log_warning(f"Failed to validate message: {e}")

    def _get_json_output_prompt(self) -> str:
        """Return the JSON output prompt for the Agent.

        This is added to the system prompt when the response_model is set and structured_outputs is False.
        """
        import json

        json_output_prompt = (
            "Provide your output as a JSON containing the following fields:"
        )
        if self.response_model is not None:
            if isinstance(self.response_model, str):
                json_output_prompt += "\n<json_fields>"
                json_output_prompt += f"\n{self.response_model}"
                json_output_prompt += "\n</json_fields>"
            elif isinstance(self.response_model, list):
                json_output_prompt += "\n<json_fields>"
                json_output_prompt += f"\n{json.dumps(self.response_model)}"
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
                        json_output_prompt += f"\n{json.dumps([key for key in response_model_properties.keys() if key != '$defs'])}"
                        json_output_prompt += "\n</json_fields>"
                        json_output_prompt += (
                            "\n\nHere are the properties for each field:"
                        )
                        json_output_prompt += "\n<json_field_properties>"
                        json_output_prompt += (
                            f"\n{json.dumps(response_model_properties, indent=2)}"
                        )
                        json_output_prompt += "\n</json_field_properties>"
            else:
                log_warning(f"Could not build json schema for {self.response_model}")
        else:
            json_output_prompt += "Provide the output as JSON."

        json_output_prompt += "\nStart your response with `{` and end it with `}`."
        json_output_prompt += "\nYour output will be passed to json.loads() to convert it to a Python object."
        json_output_prompt += "\nMake sure it only contains valid JSON."
        return json_output_prompt
