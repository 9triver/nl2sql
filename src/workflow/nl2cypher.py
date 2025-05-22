import asyncio
import os
from typing import Any, Dict, Iterator, List, Literal, Optional, Union

from agno.memory.v2.memory import Memory
from agno.memory.workflow import WorkflowMemory
from agno.run.team import TeamRunResponse
from agno.storage.base import Storage
from agno.utils.log import log_error, log_info
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

    def expand(self, question: str, state: TreeState, num: int) -> TreeState:
        root = state.root
        best_candidate: Node = root.best_child if root.children else root
        reason_trace = "\n".join(best_candidate.get_trajectory())
        message = f"用户问题:{question}\n\n推理历史:\n{reason_trace}"

        async def _generate_single_candidate():
            """Generate One candidate and Reflect on it"""
            cypher_tree_team = get_cypher_tree_team()
            result = await cypher_tree_team.arun(message=message)
            candidate = str(result.content).strip()
            reflection = self.reflection_chain(input=state.input, candidate=candidate)
            return candidate, reflection

        async def _generate_candidates():
            tasks = [_generate_single_candidate() for _ in range(num)]
            return await asyncio.gather(*tasks)

        results = asyncio.run(_generate_candidates())

        # Grow tree
        child_nodes = [
            Node(
                [candidate],
                parent=best_candidate,
                reflection=reflection,
            )
            for candidate, reflection in results
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
