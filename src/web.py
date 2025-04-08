from fastapi import FastAPI
from agent.cypher.cypher_team import CypherTeam

app = FastAPI()

cypher_team = CypherTeam()


@app.get("/ask")
async def ask(query: str):
    response = cypher_team.run(query)
    return {"response": response.content}
