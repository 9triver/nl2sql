from agent.cypher.cypher_team import CypherTeam
from prompt_toolkit import PromptSession

if __name__ == "__main__":
    cypher_team = CypherTeam()
    session = PromptSession("输入你的问题或输入Q退出\n🧑")
    while True:
        message = session.prompt()
        if len(message) == 0:
            continue
        if message == "Q":
            break
        cypher_team.print_response(message=message, stream=True)
