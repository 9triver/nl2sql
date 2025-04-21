import json, os
from typing import Dict, Optional, Iterator, Union, Any

from agno.memory.v2.memory import Memory
from agno.memory.workflow import WorkflowMemory
from agno.storage.base import Storage
from pydantic import BaseModel, Field


from agno.agent import Agent
from agno.team import TeamRunResponse
from agno.models.openai import OpenAIChat
from agno.workflow import Workflow, RunResponse, RunEvent
from storage.yaml import YamlStorage
from agno.utils.log import logger
from agent.question_validator import QuestionValidatorAgent, ValidateResult
from utils.utils import get_cypher_team, get_validator, get_validate_message


class NL2CypherWorkflow(Workflow):
    cypher_team = get_cypher_team()
    validator = get_validator()
    database_dir = "./tmp"

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        workflow_id: Optional[str] = None,
        description: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
        session_state: Optional[Dict[str, Any]] = None,
        memory: Optional[Union[WorkflowMemory, Memory]] = None,
        storage: Optional[Storage] = YamlStorage(
            dir_path=os.path.join(database_dir, "workflow"), mode="workflow"
        ),
        extra_data: Optional[Dict[str, Any]] = None,
        debug_mode: bool = True,
        monitoring: bool = False,
        telemetry: bool = False,
    ):
        super().__init__(
            name=name,
            workflow_id=workflow_id,
            description=description,
            user_id=user_id,
            session_id=session_id,
            session_name=session_name,
            session_state=session_state,
            memory=memory,
            storage=storage,
            extra_data=extra_data,
            debug_mode=debug_mode,
            monitoring=monitoring,
            telemetry=telemetry,
        )

    def run(self, question: str, retries: int = 3) -> Iterator[RunResponse]:
        """This is where the main logic of the workflow is implemented."""
        logger.info(f"user question: {question}")
        validate_result = ValidateResult(success="unsuccuss", explanation="")
        for _ in range(retries):
            if validate_result.success == "success":
                break

            logger.info(f"cypher_team start\n")
            team_message = question
            if len(validate_result.explanation) > 0:
                team_message = f"You don't answer my question sucessfully, Explanation: {validate_result.explanation}, Question: {question}"

            response = self.cypher_team.run(
                message=team_message, stream=True, stream_intermediate_steps=True
            )

            reponse_content = ""
            for r in response:
                if (
                    r.content is not None
                    and isinstance(r.content, str)
                    and len(r.content) > 0
                ):
                    reponse_content += str(r.content)
                yield RunResponse(run_id=self.run_id, content=r.content)

            logger.info(f"question_validate start\n")
            validate_message = get_validate_message(
                question=question, response=reponse_content
            )
            validate_result = self.validator.run(message=validate_message).content
