from os import getenv

import yaml


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
        model_name = response_model_config["model_name"]
        self.response_model_name = getenv(model_name or "") or f"load_{model_name}_fail"
        base_url = response_model_config["base_url"]
        self.response_base_url = getenv(base_url or "") or f"load_{base_url}_fail"
        api_key = response_model_config["api_key"]
        self.response_api_key = getenv(api_key or "") or f"load_{api_key}_fail"
        # embed model
        embed_model_config = model_config["embed_model"]
        model_name = embed_model_config["model_name"]
        self.embed_model_name = getenv(model_name or "") or f"load_{model_name}_fail"
        base_url = embed_model_config["base_url"]
        self.embed_base_url = getenv(base_url or "") or f"load_{base_url}_fail"
        api_key = embed_model_config["api_key"]
        self.embed_api_key = getenv(api_key or "") or f"load_{api_key}_fail"
        return

    def parse_database_config(self, database_config):
        self.DATABASE_URL = getenv(database_config["URL"])
        self.DATABASE_USER = getenv(database_config["USER"])
        self.DATABASE_PASSWORD = getenv(database_config["PASSWORD"])
        self.DATABASE_NAME = getenv(database_config["NAME"])
        return
