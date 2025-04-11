import yaml
from agno.storage.yaml import YamlStorage as AgnoYamlStorage


class YamlStorage(AgnoYamlStorage):
    def serialize(self, data: dict) -> str:
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    def deserialize(self, data: str) -> dict:
        return yaml.safe_load(data)
