from agno.memory.v2.manager import MemoryManager as AgnoMemoryManager

from textwrap import dedent
from typing import Any, Dict, List, Optional

from agno.models.message import Message


class MemoryManager(AgnoMemoryManager):

    def get_system_message(
        self,
        existing_memories: Optional[List[Dict[str, Any]]] = None,
        enable_delete_memory: bool = True,
        enable_clear_memory: bool = True,
    ) -> Message:
        if self.system_message is not None:
            return Message(role="system", content=self.system_message)

        memory_capture_instructions = self.memory_capture_instructions or dedent(
            """\
            记忆应包含可用于个性化用户交互的详细信息，例如：
              - 个人基本信息：name, age, occupation, location, interests, preferences 等
              - 用户分享的重要人生事件或经历
              - 关于用户当前状况、挑战或目标的重要背景信息
              - 用户的喜好厌恶、观点立场、信念价值观等
              - 其他能深入体现用户个性特征、思维视角或核心需求的重要细节\
        """
        )

        # -*- Return a system message for the memory manager
        system_prompt_lines = [
            "你是负责管理用户关键信息的 MemoryManager。"
            "你将收到需要捕获记忆的标准（在<memories_to_capture>部分）和现有记忆列表（在<existing_memories>部分）。",
            "",
            "## 添加或更新记忆的时机",
            "- 你的首要任务是基于用户消息决定是否需要添加、更新或删除记忆，或者无需任何更改",
            "- 如果用户消息符合<memories_to_capture>中的标准，且该信息尚未被<existing_memories>捕获，则应将其作为记忆捕获",
            "- 如果用户消息不符合<memories_to_capture>中的标准，则无需更新记忆",
            "- 如果<existing_memories>中的现有记忆已捕获所有相关信息，则无需更新记忆",
            "",
            "## 如何添加或更新记忆",
            "- 若要添加新记忆，请创建能捕获关键信息的记忆，就像为将来参考而存储一样",
            "- 记忆应是简洁的第三人称陈述句，概括用户输入的最重要方面，不添加额外信息",
            "  - 示例：用户消息是'I'm going to the gym'，记忆可以是`John Doe regularly goes to the gym`",
            "  - 示例：用户消息是'My name is John Doe'，记忆可以是`User's name is John Doe`",
            "- 单个记忆不宜过长或复杂，如需捕获多个信息请创建多个记忆",
            "- 避免在多个记忆中重复相同信息，必要时更新现有记忆",
            "- 若用户要求更新或忘记某个记忆，请移除所有相关引用，不要使用'The user used to like...`这类表述",
            "- 更新记忆时，应在现有记忆基础上追加新信息，而非完全覆盖",
            "- 当用户偏好变化时，更新相关记忆反映新偏好，同时需记录用户过去的偏好及其变化",
            "",
            "## 记忆创建标准",
            "使用以下标准判断用户消息是否应被捕获为记忆",
            "",
            "<memories_to_capture>",
            memory_capture_instructions,
            "</memories_to_capture>",
            "",
            "## 更新记忆操作",
            "你将在<existing_memories>部分收到现有记忆列表，你可以：",
            "  1. 决定不进行任何更改",
            "  2. 使用`add_memory`工具添加新记忆",
            "  3. 使用`update_memory`工具更新现有记忆",
        ]
        if enable_delete_memory:
            system_prompt_lines.append(
                "  4. 如需删除现有记忆，使用 `delete_memory` 工具"
            )
        if enable_clear_memory:
            system_prompt_lines.append(
                "  5. 如需清除所有记忆，使用 `clear_memory` 工具"
            )
        system_prompt_lines += [
            "你可以在单个响应中调用多个工具。",
            "仅在需要记录用户提供的关键信息时，才添加或更新记忆。",
        ]

        if existing_memories and len(existing_memories) > 0:
            system_prompt_lines.append("\n<existing_memories>")
            for existing_memory in existing_memories:
                system_prompt_lines.append(f"ID: {existing_memory['memory_id']}")
                system_prompt_lines.append(f"记忆内容: {existing_memory['memory']}")
                system_prompt_lines.append("")
            system_prompt_lines.append("</existing_memories>")

        if self.additional_instructions:
            system_prompt_lines.append(self.additional_instructions)

        return Message(role="system", content="\n".join(system_prompt_lines))
