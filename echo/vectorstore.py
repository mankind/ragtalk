
import logging
from django.conf import settings
from langchain_community.vectorstores import Chroma
import chromadb
from chromadb.config import Settings  
import os 

logger = logging.getLogger(__name__)

os.environ["CHROMA_TELEMETRY"] = "false"

class VectorStoreService:
    """
    Wrapper around Chroma to avoid tight coupling.
    Allows easy replacement with Pinecone / Weaviate later.
    """

    def __init__(self, embeddings):
        self.embeddings = embeddings

        self.vector_store = Chroma(
            collection_name="document_collection",
            embedding_function=embeddings,
            persist_directory=settings.CHROMA_DB_DIR
        )

    def add_documents(self, documents):
        """
        Persist document chunks to Chroma.
        """
        try:
            self.vector_store.add_documents(documents)
            # self.vector_store.persist()
        except Exception as exc:
            logger.exception("Failed to persist documents to Chroma")
            raise exc
            
    def search(self, query: str, k: int = 4, metadata_filter: dict = None):
        """
        Similarity search returning documents and confidence scores.
        
        Args:
            query: The natural language string to search for.
            k: Number of chunks to retrieve (default: 4).
            metadata_filter: Optional dict for metadata filtering (e.g. {"source": "doc_id"}).
        """
        # Lead approach: similarity_search_with_score provides the 'distance' 
        # allowing the LLM/System to judge context relevance.
        return self.vector_store.similarity_search_with_score(
            query, 
            k=k, 
            filter=metadata_filter
        )

    def search_by_vector(self, embedding: list, k: int = 4, metadata_filter: dict = None):
        """
        Search using a pre-calculated vector.
        Useful for advanced RAG patterns like HyDE (Hypothetical Document Embeddings).
        """
        return self.vector_store.similarity_search_by_vector(
            embedding, 
            k=k, 
            filter=metadata_filter
        )
