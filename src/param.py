import yaml
from os import getenv


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
        models_config = config["models"]
        self.parse_models_config(models_config)
        # database config
        database_config = config["database"]
        self.parse_database_config(database_config)
        return

    def parse_models_config(self, model_config):
        # response_model
        response_model_config = model_config["response_model"]
        self.response_model_name = response_model_config["model_name"]
        self.response_base_url = response_model_config["base_url"]
        api_key_name = response_model_config["api_key_name"]
        self.response_api_key = (
            getenv(api_key_name or "") or f"load_{api_key_name}_fail"
        )
        # embed model
        embed_model_config = model_config["embed_model"]
        self.embed_model_name = embed_model_config["model_name"]
        self.embed_base_url = embed_model_config["base_url"]
        api_key_name = embed_model_config["api_key_name"]
        self.embed_api_key = getenv(api_key_name or "") or f"load_{api_key_name}_fail"
        return

    def parse_database_config(self, database_config):
        self.DATABASE_URL = database_config["URL"]
        self.DATABASE_USER = database_config["USER"]
        self.DATABASE_PASSWORD = database_config["PASSWORD"]
        self.DATABASE_NAME = database_config["NAME"]
        return
