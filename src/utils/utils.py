from agno.models.openai import OpenAILike


def get_model(api_key: str, base_url: str, model_name: str):
    return OpenAILike(id=model_name, base_url=base_url, api_key=api_key)
