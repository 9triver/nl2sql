import gradio as gr
from gradio import ChatMessage
from agent.cypher.cypher_team import CypherTeam
from agno.run.team import TeamRunResponse
from datetime import datetime
from loguru import logger

USER_AVATAR = "./assets/user.png"
FAVICON = "./assets/robot.png"


class ChatUI:
    def __init__(self, cypher_team: CypherTeam) -> None:
        self.cypher_team = cypher_team
        self.currentDateAndTime = datetime.now()
        self.app = self._build_chatui(get_response=self.get_stream_response)

    def run(self) -> None:
        self.app.queue(default_concurrency_limit=3).launch(
            inbrowser=True,
            share=False,
            favicon_path=FAVICON,
            server_name="0.0.0.0",
            server_port=7861,
        )

    async def get_stream_response(
        self,
        message: str,
        history: str,
    ):
        think_message = ChatMessage(
            content="",
            role="assistant",
            metadata={"title": f"Think ...", "id": 0, "status": "done"},
        )
        chat_message = ChatMessage(
            content="", role="assistant", metadata={"id": 1, "status": "done"}
        )

        try:
            response = await self.cypher_team.arun(
                message=message, stream_intermediate_steps=True, stream=True
            )
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            chat_message.content += "\n出错了!"
            yield chat_message
            return

        async for chunk in response:
            member_responses = chunk.member_responses
            formatted_tool_calls = chunk.formatted_tool_calls
            content = chunk.content

            if member_responses is not None and len(member_responses) > 0:
                member_messages = [
                    member_response.content for member_response in member_responses
                ]
                member_messages = (
                    "Member Response:\n" + "\n".join(member_messages) + "\n"
                )
                if not think_message.content.endswith(member_messages):
                    think_message.content += member_messages
            elif formatted_tool_calls is not None:
                tool_used_messages = (
                    "Use tool:\n" + "\n".join(formatted_tool_calls) + "\n"
                )
                if not think_message.content.endswith(tool_used_messages):
                    think_message.content += tool_used_messages
            elif content is not None:
                if content == "Run started":
                    content += "\n"
                chat_message.content += content

            if len(think_message.content) > 0:
                yield [think_message, chat_message]
            else:
                yield chat_message

    def _build_chatui(self, get_response):
        with gr.Blocks(
            theme=gr.themes.Soft(primary_hue="blue", neutral_hue="zinc")
        ) as app:
            gr.HTML(f"<h1>Neo4j Agent Version: {self.currentDateAndTime}</h1>")
            chatbot = gr.Chatbot(
                height=540,
                avatar_images=(USER_AVATAR, FAVICON),
                type="messages",
                label="Cypher Team",
            )
            gr.ChatInterface(
                fn=get_response,
                type="messages",
                chatbot=chatbot,
                textbox=gr.Textbox(
                    placeholder="Type your question here...",
                    container=False,
                    scale=7,
                    autofocus=True,
                ),
            )
        return app
