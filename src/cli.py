from prompt_toolkit import PromptSession
from utils.utils import get_cypher_team

if __name__ == "__main__":
    cypher_team = get_cypher_team()
    session = PromptSession("输入你的问题或输入Q退出\n🧑")
    while True:
        message = session.prompt()
        if len(message) == 0:
            continue
        if message == "Q":
            break
        cypher_team.print_response(message=message, stream=True)
