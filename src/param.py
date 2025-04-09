import yaml
from typing import List


class Parameter:
    def __init__(self, config_file_path=None) -> None:
        if config_file_path is None:
            return
        with open(file=config_file_path, mode="r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        self.parse_config(config=config)

    @classmethod
    def parse(cls, config_file_path):
        if config_file_path is None:
            return
        with open(file=config_file_path, mode="r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        para_config = Parameter()
        para_config.parse_config(config=config)
        return para_config

    def parse_config(self, config):
        # model config
        model_config = config["model"]
        self.parse_model_config(model_config)
        # database config
        database_config = config["database"]
        self.parse_database_config(database_config)
        return

    def parse_model_config(self, model_config):
        self.model_api_key_name = model_config["api_key_name"]
        self.model_api_base_url = model_config["api_base_url"]
        self.model_name = model_config["model_name"]
        return

    def parse_database_config(self, database_config):
        self.DATABASE_URL = database_config["URL"]
        self.DATABASE_USER = database_config["USER"]
        self.DATABASE_PASSWORD = database_config["PASSWORD"]
        self.DATABASE_NAME = database_config["NAME"]
        return
