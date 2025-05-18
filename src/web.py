from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from utils.utils import get_run_response_content
from workflow.nl2cypher import NL2CypherWorkflow

app = FastAPI()

workflow = NL2CypherWorkflow()


@app.get("/ask")
async def ask(question: str):
    def workflow_streamer():
        run_response = workflow.run(question=question)
        for resp in run_response:
            run_response_content = get_run_response_content(run_response=resp)
            if run_response_content != "Run started":
                yield run_response_content

    return StreamingResponse(workflow_streamer())
