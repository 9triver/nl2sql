from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from typing import Iterator, Union
from agno.workflow import RunResponse
from agno.run.team import TeamRunResponse

from workflow.nl2cypher import NL2CypherWorkflow
from utils.utils import get_run_response_content

app = FastAPI()

workflow = NL2CypherWorkflow()


@app.get("/ask")
async def ask(question: str):

    def workflow_streamer():
        run_response: Iterator[Union[RunResponse, TeamRunResponse]] = workflow.run(
            question=question, retries=0
        )
        for resp in run_response:
            run_response_content = get_run_response_content(run_response=resp)
            if run_response_content != "Run started":
                yield run_response_content

    return StreamingResponse(workflow_streamer())
