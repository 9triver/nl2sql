from utils.utils import get_cypher_team
from fastapi import FastAPI

app = FastAPI()

cypher_team = get_cypher_team()


@app.get("/ask")
async def ask(query: str):
    response = cypher_team.run(query)
    return {"response": response.content}
