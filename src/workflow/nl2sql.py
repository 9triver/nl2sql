import json
from typing import Optional, Iterator

from pydantic import BaseModel, Field

from agent.sql.schema_linker import SchemaLinkerAgent, Schema
from agent.sql.sql_generator import SQLGeneratorAgent
from agent.sql.sql_executor import SQLExecutorAgent
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.workflow import Workflow, RunResponse, RunEvent
from agno.storage.workflow.sqlite import SqliteWorkflowStorage
from agno.utils.pprint import pprint_run_response
from loguru import logger


class NL2SQL(Workflow):
    schema_linker: SchemaLinkerAgent = SchemaLinkerAgent()
    generator: SQLGeneratorAgent = SQLGeneratorAgent()
    executor: SQLExecutorAgent = SQLExecutorAgent()

    def run(self, query: str) -> Iterator[RunResponse]:
        """This is where the main logic of the workflow is implemented."""
        logger.info(f"nl2sql: {query}")

        schemas: Optional[Schema] = self._link_schema(query)
        if schemas is None or len(schemas.schemas) == 0:
            yield RunResponse(
                event=RunEvent.workflow_completed,
                content=f"Sorry, could not find any schema on the query: {query}",
            )
            return

    def _link_schema(self, query: str) -> Optional[Schema]:
        MAX_ATTEMPTS = 3

        for attempt in range(MAX_ATTEMPTS):
            try:
                linker_response: RunResponse = self.schema_linker.run(query)

                # Check if we got a valid response
                if not linker_response or not linker_response.content:
                    logger.warning(
                        f"Attempt {attempt + 1}/{MAX_ATTEMPTS}: Empty linker response"
                    )
                    continue
                # Check if the response is of the expected SearchResults type
                if not isinstance(linker_response.content, Schema):
                    logger.warning(
                        f"Attempt {attempt + 1}/{MAX_ATTEMPTS}: Invalid response type"
                    )
                    continue

                schema_count = len(linker_response.content.schemas)
                logger.info(f"Found {schema_count} schema on attempt {attempt + 1}")
                return linker_response.content

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{MAX_ATTEMPTS} failed: {str(e)}")

        logger.error(f"Failed to get schema results after {MAX_ATTEMPTS} attempts")
        return None


# Run the workflow if the script is executed directly
if __name__ == "__main__":
    from rich.prompt import Prompt
