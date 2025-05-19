import asyncio
import collections.abc
import os
from types import GeneratorType
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional, Union, cast
from uuid import uuid4

from agno.memory.v2.memory import Memory
from agno.memory.workflow import WorkflowMemory, WorkflowRun
from agno.run.team import TeamRunResponse
from agno.storage.base import Storage
from agno.utils.log import log_debug, log_error, log_info, log_warning
from agno.workflow import RunResponse, Workflow

from agent.reflector import Reflection, ReflectorAgent
from storage.yaml import YamlStorage
from utils.utils import get_cypher_tree_team, get_reflector
from workflow.tree import Node, TreeState


class NL2CypherWorkflow(Workflow):
    reflector = get_reflector()
    database_dir = "./tmp"
    storage = YamlStorage(
        dir_path=os.path.join(database_dir, "workflow"), mode="workflow"
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
        memory: Optional[Union[WorkflowMemory, Memory]] = None,
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
        self, question: str, search_depth: int = 5, expand_num: int = 3
    ) -> Iterator[Union[RunResponse, TeamRunResponse]]:
        """This is where the main logic of the workflow is implemented."""
        log_info(f"Processing question: {question}")
        result = self.run_lats(
            question=question, search_depth=search_depth, expand_num=expand_num
        )
        log_info(f"LATS algorithm completed. Result: {result}...")

        yield RunResponse(run_id=self.run_id, content=result)

    def reflection_chain(
        self, input: str, candidate: Optional[Union[str, List[str]]] = None
    ) -> Reflection:
        """Generates reflection on Cypher query generation process by analyzing input and candidate.

        Processes either a single candidate query or the last entry from a list of candidates,
        then generates quality assessment and improvement suggestions.

        Args:
            input: Original natural language input from the user
            candidate: Candidate Cypher query(ies) to evaluate. Can be:
                - Single query string
                - List of query strings
                - None for direct input analysis

        Returns:
            Reflection: Object containing:
                - plan: Textual analysis and plan of the candidate
                - score: Quality score between 0-1
                - end: Whether candidate satisfies requirements
        """
        try:
            candidate_content = ""
            if candidate:
                candidate_content = (
                    candidate[-1] if isinstance(candidate, list) else candidate
                )

            message = self.reflection_prompt.format(
                input=input, candidate=candidate_content
            )
            reflection: Reflection = self.reflector.run(message=message).content
            log_info(f"reflection:{reflection}")
            return reflection
        except Exception as e:
            log_error(f"Error in reflection_chain: {e!s}", exc_info=True)
            return Reflection(plan=f"Error in reflection: {e!s}", score=0, end=False)

    def generate_initial_response(self, state: TreeState) -> TreeState:
        """Generates the initial response and reflection for the conversation flow.

        Processes the input state through the Cypher generation team workflow,
        creates an initial response node with reflection, and constructs the
        initial conversation tree structure.

        Args:
            state: The current conversation state containing user input and
                conversation history. Expects state.input to contain the latest
                user query.

        Returns:
            TreeState: Updated state containing the root node with initial response,
                reflection metadata, and original input. Returns empty root node
                on processing errors.
        """
        state_input = state.input
        cypher_tree_team = get_cypher_tree_team()
        try:
            team_response = cypher_tree_team.run(message=state_input)
            team_response_content = str(team_response.content).strip()
            log_info(f"Initial Response:{team_response_content}")

            # Generate reflection
            reflection = self.reflection_chain(
                input=state_input, candidate=team_response_content
            )

            # Create Node with messages as a list containing a single dict
            messages = [team_response_content]
            root = Node(messages=messages, reflection=reflection)

            return TreeState(root=root, input=state_input)
        except Exception as e:
            log_error(f"Error generating initial response: {e!s}", exc_info=True)
            return TreeState(root=None, input=state_input)

    def generate_candidates(
        self, question: str, messages: List[str], num: int
    ) -> List[str]:
        """Generates multiple candidate Cypher queries through parallel execution.

        Uses asynchronous tasks to generate potential Cypher query candidates based
        on the most recent message. Implements error handling and fallback values
        for failed generations.

        Args:
            question: Natural language input describing the user's question
            messages: Conversation history containing natural language messages
            num: Number of candidate queries to generate in parallel

        Returns:
            List of generated Cypher queries or error placeholders. Each entry will be:
            - A valid Cypher query string if generation succeeds
            - "Failed to generate candidate." if any error occurs
        """
        message = f"用户问题:{question}\n\n推理历史:\n{'\n'.join(messages)}"

        async def _wrap_team_arun(message: str):
            cypher_tree_team = get_cypher_tree_team()
            return await cypher_tree_team.arun(message=message)

        async def _agenerate_candidates():
            tasks = [_wrap_team_arun(message) for _ in range(num)]
            return await asyncio.gather(*tasks)

        results = asyncio.run(_agenerate_candidates())
        # results = []
        # for _ in range(num):
        #     cypher_tree_team = get_cypher_tree_team()
        #     results.append(cypher_tree_team.run(message=message))

        candidates = [
            str(result.content).strip()
            if not isinstance(result, Exception)
            else "Failed to generate candidate."
            for result in results
        ]
        return candidates

    def expand(self, question: str, state: TreeState, num: int) -> TreeState:
        """Expand the search tree by generating and evaluating new Cypher query candidates.

        Args:
            question: Natural language input describing the user's question
            state: Current state of the exploration tree containing query candidates
            num: Number of new candidates to generate and evaluate (must be > 0)

        Returns:
            Updated tree state with new candidate nodes added to the best existing branch
        """
        root = state.root
        best_candidate: Node = root.best_child if root.children else root
        messages = best_candidate.get_trajectory()

        # Generate N candidates
        new_candidates = self.generate_candidates(
            question=question, messages=messages, num=num
        )

        # Reflect on each candidate
        # tasks = [
        #     self.reflection_chain(input=state.input, candidate=candidate)
        #     for candidate in new_candidates
        # ]
        # reflections = asyncio.run(asyncio.gather(*tasks))
        reflections = []
        for candidate in new_candidates:
            reflection = self.reflection_chain(input=state.input, candidate=candidate)
            reflections.append(reflection)

        # Grow tree
        child_nodes = [
            Node(
                [candidate],
                parent=best_candidate,
                reflection=reflection,
            )
            for candidate, reflection in zip(new_candidates, reflections)
        ]
        log_info(f"expand_nodes:{child_nodes}")
        best_candidate.children.extend(child_nodes)
        return state

    def should_loop(self, state: TreeState) -> Literal["expand", "end"]:
        """Determine whether to continue the tree search."""
        root = state.root
        if root.is_solved:
            return "end"
        if root.height > 5:
            return "end"
        return "expand"

    def run_lats(self, question: str, search_depth: int = 5, expand_num: int = 3):
        """Execute the Language Agent Tree Search (LATS) process for generating Cypher queries.

        Implements a multi-step search algorithm that combines language model reasoning with
        graph-based exploration to refine and validate Cypher query generation.

        Args:
            question: Natural language input describing the user's question
            search_depth: Maximum depth for the search tree exploration (default: 5)
            expand_num: Number of nodes to expand at each depth level (default: 3)

        Returns:
            str: The final validated Cypher query string or error message
        """
        state = TreeState(root=None, input=question)
        state = self.generate_initial_response(state=state)
        if not isinstance(state, TreeState) or state.root is None:
            return "Failed to generate initial response due to an unexpected error."

        for depth in range(search_depth):
            action = self.should_loop(state)
            if action == "end":
                log_info(f"Search ended after {depth + 1} depth")
                break
            state = self.expand(question=question, state=state, num=expand_num)

        if not isinstance(state, TreeState) or state.root is None:
            return "No valid solution found due to an error in the search process."

        solution_node = state.root.get_best_solution()
        best_trajectory = solution_node.get_trajectory(include_reflections=False)
        if not best_trajectory:
            return "No solution found in the search process."

        result = best_trajectory[-1]
        return result

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
