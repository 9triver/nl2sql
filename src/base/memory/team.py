from dataclasses import dataclass
from typing import Optional

from agno.memory.team import TeamMemory as AgnoTeamMemory


@dataclass
class TeamMemory(AgnoTeamMemory):
    member_interaction_num: Optional[int] = None

    def get_team_member_interactions_str(self) -> str:
        team_member_interactions_str = ""
        if self.team_context and self.team_context.member_interactions:
            team_member_interactions_str += "<member_interactions>\n"

            for interaction in self.team_context.member_interactions[
                : self.member_interaction_num
            ]:
                team_member_interactions_str += f"Member: {interaction.member_name}\n"
                team_member_interactions_str += f"Task: {interaction.task}\n"
                team_member_interactions_str += (
                    f"Response: {interaction.response.to_dict().get('content', '')}\n"
                )
                team_member_interactions_str += "\n"
            team_member_interactions_str += "</member_interactions>\n"
        return team_member_interactions_str
