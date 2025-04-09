from agent.cypher.cypher_team import CypherTeam
from agent.cypher.cypher_generator import CypherGeneratorAgent
from param import Parameter
from fastapi import FastAPI

app = FastAPI()

param = Parameter(config_file_path="./config.yaml")
cypher_generator = CypherGeneratorAgent(param=param)
cypher_team = CypherTeam(param=param, members=[cypher_generator])


@app.get("/ask")
async def ask(query: str):
    response = cypher_team.run(query)
    return {"response": response.content}
