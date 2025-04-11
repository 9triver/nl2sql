from agent.cypher.cypher_team import CypherTeam
from agent.cypher.cypher_generator import CypherGeneratorAgent
from param import Parameter
from utils.utils import get_model
from fastapi import FastAPI

app = FastAPI()

param = Parameter(config_file_path="./config.yaml")
model = get_model(
    api_key=param.model_api_key,
    base_url=param.model_base_url,
    model_name=param.model_name,
)
cypher_generator = CypherGeneratorAgent(param=param, model=model)
cypher_team = CypherTeam(param=param, model=model, members=[cypher_generator])


@app.get("/ask")
async def ask(query: str):
    response = cypher_team.run(query)
    return {"response": response.content}
