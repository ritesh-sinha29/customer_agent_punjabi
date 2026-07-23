import logging
from typing import Any, Dict, List

from pinecone import Pinecone, ServerlessSpec

from src.app.core.config import settings

logger = logging.getLogger("PineconeService")


class PineconeService:
    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.index_name = settings.PINECONE_INDEX_NAME
        self.pc = None
        self.index = None
        self.supports_sparse = True

        if self.api_key:
            try:
                self.pc = Pinecone(api_key=self.api_key, pool_threads=30)
                # Note: We do not initialize the index immediately if it needs to be created
                if self.index_name:
                    self.initialize_index()
            except Exception as e:
                logger.error(f"Error initializing Pinecone: {e}")

    def initialize_index(self):
        """
        Attempts to bind to the specified index.
        """
        try:
            self.index = self.pc.Index(self.index_name, pool_threads=30)
        except Exception as e:
            logger.warning(
                f"Index '{self.index_name}' could not be bound (may not exist yet): {e}"
            )

    def get_index(self):
        return self.index

    def ensure_index(self, dimension: int = 1024, metric: str = "dotproduct") -> bool:
        """
        Ensures that the Pinecone index exists.
        If it does not exist, creates a Serverless Index with the correct dimension.
        """
        if not self.pc:
            logger.error("Pinecone client is not initialized.")
            return False

        try:
            # List existing indexes
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                logger.info(
                    f"[Step 6 - Pinecone] Creating Serverless Index '{self.index_name}' (dim={dimension}, metric={metric})..."
                )
                # Create index with serverless spec
                self.pc.create_index(
                    name=self.index_name,
                    dimension=dimension,
                    metric=metric,
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1",  # Default serverless region
                    ),
                )
                logger.info(
                    f"[Step 6 - Pinecone] Index '{self.index_name}' created successfully."
                )
            else:
                logger.info(
                    f"[Step 6 - Pinecone] Index '{self.index_name}' already exists."
                )

            # Rebind index handle
            self.initialize_index()
            return True

        except Exception as e:
            logger.error(f"Failed to check/create Pinecone index: {e}")
            return False

    def delete_by_doc_id(self, doc_id: str, namespace: str = None) -> bool:
        """
        Deletes all vector chunks matching a specific doc_id from a namespace.
        Ensures old versions of a document do not leave orphan/stale chunks.
        """
        if not self.index:
            logger.error("Pinecone index is not initialized.")
            return False

        logger.info(
            f"[Step 6 - Pinecone] Purging existing vectors for doc_id={doc_id} in namespace='{namespace or 'default'}'..."
        )
        try:
            # Delete by metadata filter
            self.index.delete(filter={"doc_id": {"$eq": doc_id}}, namespace=namespace)
            logger.info(f"[Step 6 - Pinecone] Purge completed for doc_id={doc_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors by doc_id: {e}")
            return False

    def delete_by_user_id(self, user_id: str, namespace: str = None) -> bool:
        """
        Deletes all vector chunks matching a specific user_id from a namespace.
        Used for purging and rebuilding user memory.
        """
        if not self.index:
            logger.error("Pinecone index is not initialized.")
            return False

        logger.info(
            f"[Step 6 - Pinecone] Purging existing vectors for user_id={user_id} in namespace='{namespace or 'default'}'..."
        )
        try:
            # Delete by metadata filter
            self.index.delete(filter={"user_id": {"$eq": user_id}}, namespace=namespace)
            logger.info(f"[Step 6 - Pinecone] Purge completed for user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete vectors by user_id: {e}")
            return False

    def upsert_vectors(
        self, vectors: List[Dict[str, Any]], namespace: str = None
    ) -> int:
        """
        Upserts a list of vectors to Pinecone in batches of 100.
        Each vector is represented as a dictionary:
        {
            "id": str,
            "values": List[float],
            "sparse_values": {"indices": List[int], "values": List[float]} (optional),
            "metadata": Dict[str, Any]
        }
        """
        if not self.index:
            raise RuntimeError("Pinecone index is not initialized.")

        if not vectors:
            logger.warning("No vectors provided for upsert.")
            return 0

        batch_size = 100
        total_upserted = 0
        ns_str = namespace or "default"

        logger.info(
            f"[Step 6 - Pinecone] Upserting {len(vectors)} vectors in batches of {batch_size} to namespace '{ns_str}'..."
        )

        try:
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]

                # Format to Pinecone tuple/dict layout
                upsert_payload = []
                for vec in batch:
                    item = {
                        "id": vec["id"],
                        "values": vec["values"],
                        "metadata": vec["metadata"],
                    }
                    if "sparse_values" in vec and vec["sparse_values"]:
                        sparse_val = vec["sparse_values"]
                        if sparse_val.get("indices") and sparse_val.get("values"):
                            item["sparse_values"] = sparse_val
                    upsert_payload.append(item)

                res = self.index.upsert(vectors=upsert_payload, namespace=namespace)
                total_upserted += res.get("upserted_count", len(batch))

            logger.info(
                f"[Step 6 - Pinecone] Upsert completed. Total vectors upserted: {total_upserted}"
            )
            return total_upserted
        except Exception as e:
            logger.error(f"Error during Pinecone upsert: {e}")
            raise e

    def query_hybrid(
        self,
        dense_vector: List[float],
        sparse_vector: Dict[str, Any] = None,
        top_k: int = 5,
        namespace: str = "default",
        filter: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries Pinecone index with dense and sparse vectors (hybrid search).
        Returns a list of matching records with metadata.
        """
        if not self.index:
            raise RuntimeError("Pinecone index is not initialized.")
        
        target_namespace = namespace if namespace is not None else "default"
        try:
            query_args = {
                "top_k": top_k,
                "include_metadata": True,
                "namespace": target_namespace
            }
            if filter:
                query_args["filter"] = filter
            if dense_vector is not None:
                query_args["vector"] = dense_vector
            if sparse_vector is not None and self.supports_sparse:
                if sparse_vector.get("indices") and sparse_vector.get("values"):
                    query_args["sparse_vector"] = sparse_vector
                
            res = self.index.query(**query_args)
            return [match.to_dict() for match in res.get("matches", [])]
        except Exception as e:
            if "sparse" in str(e).lower() and "sparse_vector" in query_args:
                logger.warning("Pinecone index does not support sparse values. Caching capability and retrying with dense-only query.")
                self.supports_sparse = False
                query_args.pop("sparse_vector", None)
                res = self.index.query(**query_args)
                return [match.to_dict() for match in res.get("matches", [])]
            logger.error(f"Error querying Pinecone: {e}")
            raise e

    def check_connection(self) -> bool:
        if not self.pc or not self.index:
            return False
        try:
            self.index.describe_index_stats()
            return True
        except Exception as e:
            logger.warning(f"Pinecone connection check failed: {e}")
            return False


pinecone_service = PineconeService()
