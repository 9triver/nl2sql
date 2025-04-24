import gradio as gr
from typing import Iterator, Union
from gradio import ChatMessage
from datetime import datetime
from agno.workflow import RunResponse
from agno.run.team import TeamRunResponse
from loguru import logger

from workflow.nl2cypher import NL2CypherWorkflow
from utils.utils import get_run_response

USER_AVATAR = "./assets/user.png"
FAVICON = "./assets/robot.png"


class ChatUI:
    def __init__(self, workflow: NL2CypherWorkflow) -> None:
        self.workflow = workflow
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
            run_response: Iterator[Union[RunResponse, TeamRunResponse]] = (
                self.workflow.run(question=message, retries=3)
            )
        except KeyboardInterrupt as e:
            raise e
        except Exception as e:
            chat_message.content += "\n出错了!:\n"
            chat_message.content += e
            yield chat_message
            return

        for resp in run_response:
            run_response_content, other_message = get_run_response(run_response=resp)

            if run_response_content != "Run started":
                chat_message.content += run_response_content
            think_message.content += other_message
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
                label="Cypher Workflow",
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
