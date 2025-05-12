import os
import collections.abc
from types import GeneratorType
from uuid import uuid4
from typing import Dict, Optional, Iterator, Union, Any, Callable, cast

from agno.memory.v2.memory import Memory
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.workflow import WorkflowMemory, WorkflowRun
from agno.storage.base import Storage
from agno.workflow import Workflow, RunResponse
from agno.run.team import TeamRunResponse
from storage.yaml import YamlStorage
from agno.utils.log import log_debug, log_info, log_error, log_warning


from agent.question_validator import ValidateResult
from base.memory.manager import MemoryManager
from utils.utils import get_cypher_team, get_validator, get_validate_message


class NL2CypherWorkflow(Workflow):
    cypher_team = get_cypher_team()
    validator = get_validator()
    database_dir = "./tmp"
    storage = YamlStorage(
        dir_path=os.path.join(database_dir, "workflow"), mode="workflow"
    )
    memory = Memory(
        db=SqliteMemoryDb(
            table_name="workflow",
            db_file=os.path.join(database_dir, "workflow/memory.db"),
        ),
        memory_manager=MemoryManager(),
    )

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
        memory: Optional[Union[WorkflowMemory, Memory]] = memory,
        storage: Optional[Storage] = storage,
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

    def run(
        self, question: str, retries: int = 3
    ) -> Iterator[Union[RunResponse, TeamRunResponse]]:
        """This is where the main logic of the workflow is implemented."""
        if retries < 0:
            raise ValueError(f"retries must >= 0, but got {retries}")
        log_info(f"user question: {question}")
        validate_result = ValidateResult(success="未成功", explanation="")
        for _ in range(retries + 1):
            if validate_result.success == "成功":
                break

            log_info(f"cypher_team start\n")
            team_message = question
            if len(validate_result.explanation) > 0:
                team_message = f"Y你未能成功回答我的问题，错误说明: {validate_result.explanation}，原问题: {question}"

            flag = True
            try_times = 0
            exception_message = ""
            while flag and try_times < retries + 1:
                try:
                    team_run_responses = self.cypher_team.run(
                        message=team_message + exception_message,
                        stream=True,
                        stream_intermediate_steps=True,
                    )
                    team_response_content = ""
                    for team_run_response in team_run_responses:
                        if (
                            team_run_response.content is not None
                            and isinstance(team_run_response.content, str)
                            and len(team_run_response.content) > 0
                        ):
                            team_response_content += str(team_run_response.content)
                        yield team_run_response
                    flag = False
                except KeyboardInterrupt:
                    flag = False
                except Exception as e:
                    exception_message = f"\n\n在之前的交互中，你抛出了错误: {e}"
                    log_error(exception_message)
                finally:
                    try_times += 1

            validate_message = get_validate_message(
                question=question, response=team_response_content
            )
            validate_result = self.validator.run(message=validate_message).content
            log_info(f"validate_result: {validate_result}\n")
            yield RunResponse(run_id=self.run_id, content=validate_result)

    def run_workflow(self, **kwargs: Any):
        """Run the Workflow"""

        # Set mode, debug, workflow_id, session_id, initialize memory
        self.set_storage_mode()
        self.set_debug()
        self.set_workflow_id()
        self.set_session_id()
        self.initialize_memory()

        # Create a run_id
        self.run_id = str(uuid4())

        # Set run_input, run_response
        self.run_input = kwargs
        self.run_response = RunResponse(
            run_id=self.run_id, session_id=self.session_id, workflow_id=self.workflow_id
        )

        # Read existing session from storage
        self.read_from_storage()

        # Update the session_id for all Agent instances
        self.update_agent_session_ids()

        log_debug(f"Workflow Run Start: {self.run_id}", center=True)
        try:
            self._subclass_run = cast(Callable, self._subclass_run)
            result = self._subclass_run(**kwargs)
        except Exception as e:
            log_error(f"Workflow.run() failed: {e}")
            raise e

        # The run_workflow() method handles both Iterator[RunResponse] and RunResponse
        # Case 1: The run method returns an Iterator[RunResponse]
        if isinstance(result, (GeneratorType, collections.abc.Iterator)):
            # Initialize the run_response content
            self.run_response.content = ""

            def result_generator():
                self.run_response = cast(RunResponse, self.run_response)
                if isinstance(self.memory, WorkflowMemory):
                    self.memory = cast(WorkflowMemory, self.memory)
                elif isinstance(self.memory, Memory):
                    self.memory = cast(Memory, self.memory)

                for item in result:
                    if isinstance(item, RunResponse):
                        # Update the run_id, session_id and workflow_id of the RunResponse
                        item.run_id = self.run_id
                        item.session_id = self.session_id
                        item.workflow_id = self.workflow_id

                        # Update the run_response with the content from the result
                        if item.content is not None and isinstance(item.content, str):
                            self.run_response.content += item.content
                    yield item

                # Add the run to the memory
                if isinstance(self.memory, WorkflowMemory):
                    self.memory.add_run(
                        WorkflowRun(input=self.run_input, response=self.run_response)
                    )
                elif isinstance(self.memory, Memory):
                    self.memory.add_run(
                        session_id=self.session_id, run=self.run_response
                    )  # type: ignore
                # Write this run to the database
                self.write_to_storage()
                log_debug(f"Workflow Run End: {self.run_id}", center=True)

            return result_generator()
        # Case 2: The run method returns a RunResponse
        elif isinstance(result, RunResponse):
            # Update the result with the run_id, session_id and workflow_id of the workflow run
            result.run_id = self.run_id
            result.session_id = self.session_id
            result.workflow_id = self.workflow_id

            # Update the run_response with the content from the result
            if result.content is not None and isinstance(result.content, str):
                self.run_response.content = result.content

            # Add the run to the memory
            if isinstance(self.memory, WorkflowMemory):
                self.memory.add_run(
                    WorkflowRun(input=self.run_input, response=self.run_response)
                )
            elif isinstance(self.memory, Memory):
                self.memory.add_run(session_id=self.session_id, run=self.run_response)  # type: ignore
            # Write this run to the database
            self.write_to_storage()
            log_debug(f"Workflow Run End: {self.run_id}", center=True)
            return result
        else:
            log_warning(
                f"Workflow.run() should only return RunResponse objects, got: {type(result)}"
            )
            return None
