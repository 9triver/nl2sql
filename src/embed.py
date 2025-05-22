from param import Parameter
from tools.neq4j import Neo4jTools

param = Parameter(config_file_path="./config.yaml")
neo4j_tools = Neo4jTools(
    user=param.DATABASE_USER,
    password=param.DATABASE_PASSWORD,
    db_uri=param.DATABASE_URL,
    database=param.DATABASE_NAME,
    embed_model_name=param.embed_model_name,
    embed_base_url=param.embed_base_url,
    embed_api_key=param.embed_api_key,
)

neo4j_tools.embed_nodes()
