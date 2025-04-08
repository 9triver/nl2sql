import os, re
from typing import List, Optional

from textwrap import dedent
from agno.tools import Toolkit
from haystack.components.converters import TextFileToDocument
from haystack import Document as HaystackDocument
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack.document_stores.types import DuplicatePolicy


class CypherKnowledge(Toolkit):
    name = "cypher_knowledge"
    instructions = dedent(
        """\
        You have following tools:
        1. If you need to retrieve relevant cypher knowledge template, use the `seach_cypher_cheatsheet` tool.\
    """
    )

    def __init__(
        self,
        name=name,
        instructions: Optional[str] = instructions,
        add_instructions: bool = True,
        cache_results: bool = False,
        cache_ttl: int = 3600,
        cache_dir: Optional[str] = None,
        embedding_model: str = "nomic-ai/nomic-embed-text-v2-moe",
    ):
        super().__init__(
            name=name,
            instructions=instructions,
            add_instructions=add_instructions,
            cache_results=cache_results,
            cache_ttl=cache_ttl,
            cache_dir=cache_dir,
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
        Loads and processes knowledge documents from a specified directory, embeds them using SentenceTransformers,
        and stores them in a Qdrant document store.

        Args:
            base_path (str, optional): The base directory path where the knowledge documents are stored. Defaults to "./knowledge/".

        Returns:
            QdrantDocumentStore: A Qdrant document store containing the embedded knowledge documents.
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
        Retrieve relevant cypher knowledge template from Cypher cheat sheet information based on the given query.

        Args:
            query (str): The search query string.
            top_k (int, optional): The maximum number of relevant documents to return. Defaults to 5.

        Returns:
            str: A concatenated string of the top-k matching Cypher cheat sheet entries, separated by newlines.
        """
        query_embedding = self.text_embedder.run(text=query)["embedding"]
        documents = self.document_store._query_by_embedding(
            query_embedding=query_embedding, top_k=top_k
        )
        texts = [document.content for document in documents]
        return "\n\n".join(texts)
