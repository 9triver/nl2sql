import os, re
from typing import List, Optional, Callable

from agno.tools import Toolkit
from haystack.components.converters import TextFileToDocument
from haystack import Document as HaystackDocument
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack.document_stores.types import DuplicatePolicy


class CypherKnowledge(Toolkit):
    name = "cypher_knowledge"

    def __init__(
        self,
        name: str = name,
        tools: List[Callable] = [],
        instructions: Optional[str] = None,
        add_instructions: bool = False,
        include_tools: Optional[list[str]] = None,
        exclude_tools: Optional[list[str]] = None,
        cache_results: bool = False,
        cache_ttl: int = 3600,
        cache_dir: Optional[str] = None,
        auto_register: bool = False,
        embedding_model: str = "nomic-ai/nomic-embed-text-v2-moe",
    ):
        super().__init__(
            name=name,
            tools=tools,
            instructions=instructions,
            add_instructions=add_instructions,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
            cache_results=cache_results,
            cache_ttl=cache_ttl,
            cache_dir=cache_dir,
            auto_register=auto_register,
        )
        self.embedding_model = embedding_model
        self.document_store = self.load_knowledge()
        self.text_embedder = SentenceTransformersTextEmbedder(
            model=embedding_model, trust_remote_code=True
        )
        self.text_embedder.warm_up()
        self.register(self.seach_cypher_cheatsheet)
        return

    def load_knowledge(self, base_path: str = "./knowledge/") -> QdrantDocumentStore:
        """
        加载并处理指定目录下的知识文档，使用SentenceTransformers进行嵌入处理，并存储到Qdrant文档库中。

        Args:
            base_path (str, 可选): 知识文档存储的基础目录路径。默认为"./knowledge/"。

        Returns:
            QdrantDocumentStore: 包含已嵌入知识文档的Qdrant文档库实例。
        """
        paths = []
        for root, dirs, files in os.walk(base_path, topdown=False):
            for name in files:
                if name.startswith("."):
                    continue
                paths.append(os.path.join(root, name))

        converter = TextFileToDocument()
        haystack_documents: List[HaystackDocument] = converter.run(sources=paths)[
            "documents"
        ]
        texts = [haystack_document.content for haystack_document in haystack_documents]
        chunks: List[str] = []
        for text in texts:
            pattern = r"```cypher.*?(?=```cypher|\Z)"
            blocks = re.findall(pattern, text, flags=re.DOTALL)
            processed_blocks = [block.rstrip() for block in blocks]
            chunks.extend(processed_blocks)
        haystack_documents = [HaystackDocument(content=chunk) for chunk in chunks]

        embedder = SentenceTransformersDocumentEmbedder(
            model=self.embedding_model, trust_remote_code=True
        )
        embedder.warm_up()
        haystack_documents = embedder.run(documents=haystack_documents)["documents"]

        document_store = QdrantDocumentStore(
            recreate_index=False, index="cypher_cheatsheet", url="http://localhost:6333"
        )
        document_store.write_documents(
            documents=haystack_documents, policy=DuplicatePolicy.SKIP
        )
        return document_store

    def seach_cypher_cheatsheet(self, query: str, top_k: int = 5) -> str:
        """
        根据给定查询检索相关的Cypher知识模板信息。Cypher速查表内容为英文文本，请使用英文进行搜索。

        参数:
            query (str): 搜索查询字符串
            top_k (int, 可选): 最大返回相关文档数量，默认为5

        返回:
            str: 用换行符连接的前top-k个匹配的Cypher速查表条目组成的拼接字符串
        """
        query_embedding = self.text_embedder.run(text=query)["embedding"]
        documents = self.document_store._query_by_embedding(
            query_embedding=query_embedding, top_k=top_k
        )
        texts = [document.content for document in documents]
        return "\n\n".join(texts)
