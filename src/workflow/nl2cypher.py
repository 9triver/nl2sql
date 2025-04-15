import json
from typing import Optional, Iterator

from pydantic import BaseModel, Field


from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.workflow import Workflow, RunResponse, RunEvent
from agno.storage.workflow.sqlite import SqliteWorkflowStorage
from agno.utils.pprint import pprint_run_response
from utils.utils import get_cypher_team, get_validator
from agent.question_validator import QuestionValidatorAgent
from loguru import logger


class NL2Cypher(Workflow):
    cypher_team = get_cypher_team()
    validator = get_validator()

    def run(self, query: str) -> Iterator[RunResponse]:
        """This is where the main logic of the workflow is implemented."""
        logger.info(f"query: {query}")

        response = yield from self.cypher_team.run(query, stream=True)
