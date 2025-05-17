import os
import collections.abc
from types import GeneratorType
from uuid import uuid4
from typing import Dict, Optional, Literal, Iterator, Union, Any, Callable, cast

from agno.memory.v2.memory import Memory
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.workflow import WorkflowMemory, WorkflowRun
from agno.storage.base import Storage
from agno.workflow import Workflow, RunResponse
from agno.run.team import TeamRunResponse
from storage.yaml import YamlStorage
from agno.utils.log import log_debug, log_info, log_error, log_warning

from workflow.tree import TreeState, Node
from agent.reflector import Reflection, ReflectorAgent
from base.memory.manager import MemoryManager
from utils.utils import get_cypher_team, get_reflector


class NL2CypherWorkflow(Workflow):
    cypher_team = get_cypher_team()
    reflector = get_reflector()
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
        self.reflection_prompt = ReflectorAgent.get_prompt()

    def run(
        self,
        question: str,
    ) -> Iterator[Union[RunResponse, TeamRunResponse]]:
        """This is where the main logic of the workflow is implemented."""
        try:
            log_info(f"Processing question: {question}")
            result = self.run_lats(question)
            log_info(f"LATS algorithm completed. Result: {result[:100]}...")
        except Exception as e:
            result = f"An error occurred while processing the question: {e!s}"
            log_error(
                f"An error occurred while processing the question: {e!s}", exc_info=True
            )

        yield RunResponse(run_id=self.run_id, content=result)

    def reflection_chain(self, inputs: Dict[str, Any]) -> Reflection:
        """Processes input data to generate a reflection with error handling.

        Extracts candidate content from various formats, constructs a reflection prompt,
        and executes the reflection process. Gracefully handles exceptions by returning
        an error-containing Reflection object.

        Args:
            inputs: Input dictionary containing:
                - 'input': Original user input string
                - 'candidate': Query candidate which can be in multiple formats:
                    * List: Uses last item's 'content' if dict, else string representation
                    * Dict: Extracts 'content' key if available
                    * String: Used directly
                    * Other types: Converted to string

        Returns:
            Reflection: Object containing:
                - reflections: Generated analysis or error message
                - score: Confidence score (0 when error occurs)
                - found_solution: False when error occurs
        """
        try:
            candidate_content = ""
            if "candidate" in inputs:
                candidate = inputs["candidate"]
                if isinstance(candidate, list):
                    candidate_content = (
                        candidate[-1]["content"]
                        if isinstance(candidate[-1], dict)
                        and "content" in candidate[-1]
                        else str(candidate[-1])
                    )
                elif isinstance(candidate, dict):
                    candidate_content = candidate.get("content", str(candidate))
                elif isinstance(candidate, str):
                    candidate_content = candidate
                else:
                    candidate_content = str(candidate)

            message = self.reflection_prompt.format(
                input=inputs.get("input", ""), candidate=candidate_content
            )
            reflection: Reflection = self.reflector.run(message=message).content
            return reflection
        except Exception as e:
            log_error(f"Error in reflection_chain: {e!s}", exc_info=True)
            return Reflection(
                reflections=f"Error in reflection: {e!s}", score=0, found_solution=False
            )

    def generate_initial_response(self, state: TreeState) -> TreeState:
        """Generates initial response and constructs the conversation tree root node.

        Processes the user input through the Cypher team workflow, generates a reflection
        on the initial response, and constructs the initial tree structure.

        Args:
            state: Current tree state containing:
                - input: User query string to process

        Returns:
            TreeState: New state containing:
                - root: Node object with:
                    - messages: List containing initial assistant response
                    - reflection: Processed reflection on the response
                  (None if processing fails)
                - input: Preserved original user input
        """
        try:
            team_response = self.cypher_team.run(message=state["input"])
            team_response_content = str(team_response.content).strip()

            # Generate reflection
            reflection_input = {
                "input": state["input"],
                "candidate": team_response_content,
            }
            reflection = self.reflection_chain(inputs=reflection_input)

            # Create Node with messages as a list containing a single dict
            messages = [{"role": "assistant", "content": team_response_content}]
            root = Node(messages=messages, reflection=reflection)

            return TreeState(root=root, input=state["input"])
        except Exception as e:
            return TreeState(root=None, input=state["input"])

    def generate_candidates(self, messages: list, num: int):
        """Generates multiple Cypher query candidates through iterative executions.

        Args:
            messages (list): Conversation history containing interaction messages.
                            Uses the last message as input query.
            num (int): Number of candidate queries to generate

        Returns:
            list[str]: List containing either successfully generated Cypher queries
                      or error messages for failed attempts
        """
        candidates = []
        for _ in range(num):
            try:
                # Use the assistant to generate a response
                last_message = (
                    messages[-1]["content"]
                    if messages and isinstance(messages[-1], dict)
                    else str(messages[-1])
                )
                team_response = self.cypher_team.run(message=last_message)
                candidates.append(team_response)
            except Exception as e:
                log_error(f"Error generating candidate: {e!s}")
                candidates.append("Failed to generate candidate.")
        if not candidates:
            log_warning("No candidates were generated.")
        return candidates

    def expand(self, state: TreeState, num: int) -> dict:
        """Expands the search tree by generating and evaluating new candidates.

        Performs one iteration of Monte Carlo Tree Search expansion:
        1. Selects the best existing node using UCB1
        2. Generates new candidate queries using the current trajectory
        3. Creates child nodes with reflection-based evaluations
        4. Adds new nodes to the search tree

        Args:
            state: Current tree state containing root node and search context
            num: Number of candidate queries to generate in this expansion phase

        Returns:
            Updated tree state with new nodes added to the best candidate's children
        """
        root = state["root"]
        best_candidate: Node = root.best_child if root.children else root
        messages = best_candidate.get_trajectory()

        # Generate N candidates using Autogen's generate_candidates function
        new_candidates = self.generate_candidates(messages=messages, num=num)

        # Reflect on each candidate using Autogen's AssistantAgent
        reflections = []
        for candidate in new_candidates:
            reflection = self.reflection_chain(
                {"input": state["input"], "candidate": candidate}
            )
            reflections.append(reflection)

        # Grow tree
        child_nodes = [
            Node(
                [{"role": "assistant", "content": candidate}],
                parent=best_candidate,
                reflection=reflection,
            )
            for candidate, reflection in zip(new_candidates, reflections)
        ]
        best_candidate.children.extend(child_nodes)

        return state

    def should_loop(self, state: Dict[str, Any]) -> Literal["expand", "end"]:
        """Determine whether to continue the tree search."""
        root = state["root"]
        if root.is_solved:
            return "end"
        if root.height > 5:
            return "end"
        return "expand"

    def run_lats(self, input_query: str, max_iterations: int = 10, expand_num: int = 5):
        """Execute the Look Ahead Tree Search (LATS) algorithm to generate Cypher queries.

        Performs an iterative search process that combines initial response generation
        with tree expansion and reflection to refine the best Cypher query solution.

        Args:
            input_query: Natural language query to be converted to Cypher
            max_iterations: Maximum number of refinement iterations (default: 10)
            expand_num: Number of candidate expansions per iteration (default: 5)

        Returns:
            str: Valid Cypher query string or error message
        """
        try:
            state = {"input": input_query, "root": None}
            try:
                state = self.generate_initial_response(state)
                if (
                    not isinstance(state, dict)
                    or "root" not in state
                    or state["root"] is None
                ):
                    log_error(
                        "Initial response generation failed or returned invalid state"
                    )
                    return "Failed to generate initial response."
                log_info("Initial response generated successfully")
            except Exception as e:
                log_error(f"Error generating initial response: {e!s}", exc_info=True)
                return "Failed to generate initial response due to an unexpected error."

            for iteration in range(max_iterations):
                action = self.should_loop(state)
                if action == "end":
                    log_info(f"Search ended after {iteration + 1} iterations")
                    break
                try:
                    state = self.expand(state=state, num=expand_num)
                    log_info(f"Completed iteration {iteration + 1}")
                except Exception as e:
                    log_error(
                        f"Error during iteration {iteration + 1}: {e!s}", exc_info=True
                    )
                    continue

            if (
                not isinstance(state, dict)
                or "root" not in state
                or state["root"] is None
            ):
                return "No valid solution found due to an error in the search process."

            solution_node = state["root"].get_best_solution()
            best_trajectory = solution_node.get_trajectory(include_reflections=False)
            if not best_trajectory:
                return "No solution found in the search process."

            result = (
                best_trajectory[-1].get("content")
                if isinstance(best_trajectory[-1], dict)
                else str(best_trajectory[-1])
            )
            log_info("LATS search completed successfully")
            return result
        except Exception as e:
            log_error(
                f"An unexpected error occurred during LATS execution: {e!s}",
                exc_info=True,
            )
            return f"An unexpected error occurred: {e!s}"

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
