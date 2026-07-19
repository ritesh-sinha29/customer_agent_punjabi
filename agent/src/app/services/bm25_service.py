import hashlib
import json
import logging
import re
import math
from pathlib import Path
from typing import Any, Dict, List
from rank_bm25 import BM25Okapi

logger = logging.getLogger("BM25Service")


class BM25Service:
    """
    Service to generate Pinecone-compatible sparse vectors using the standard rank_bm25 library.
    Ensures that Pinecone dot-product hybrid search matches the standard BM25 ranking algorithm.
    """

    def __init__(self):
        self.k1 = 1.5
        self.b = 0.75
        self.vocab_size = 2**20  # 1M dimensional sparse space

        # File paths
        data_dir = Path(__file__).resolve().parent.parent / "data"
        self.chunks_file = data_dir / "all_chunks.json"
        self.model_file = data_dir / "bm25_model.json"

        # In-memory parameters loaded on startup
        self.avgdl = 0.0
        self.idf = {}
        self.doc_count = 0
        self.load_model()

    def tokenize(self, text: str) -> List[str]:
        """
        Consistently tokenizes text into lowercase words of length > 1.
        Uses regex matching unicode alphanumeric characters to support Punjabi and English.
        """
        if not text:
            return []
        return [t.lower() for t in re.findall(r"\w+", text) if len(t) > 1]

    def load_model(self):
        """Loads BM25 parameters from disk."""
        if self.model_file.exists():
            try:
                with open(self.model_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.avgdl = data.get("avgdl", 0.0)
                    self.idf = data.get("idf", {})
                    self.doc_count = data.get("doc_count", 0)
                logger.info(
                    f"Successfully loaded BM25 model: {self.doc_count} documents, {len(self.idf)} terms."
                )
            except Exception as e:
                logger.error(f"Failed to load BM25 model parameters: {e}")
        else:
            logger.info("No pre-existing BM25 model found. Ready to fit new documents.")

    def save_model(self):
        """Saves BM25 parameters to disk."""
        try:
            self.model_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.model_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "avgdl": self.avgdl,
                        "idf": self.idf,
                        "doc_count": self.doc_count,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"Saved BM25 model parameters to {self.model_file}")
        except Exception as e:
            logger.error(f"Failed to save BM25 model parameters: {e}")

    def fit_new_documents(self, new_texts: List[str]):
        """
        Appends new text chunks to the local corpus, fits BM25Okapi from rank_bm25,
        and persists the updated IDF/average-length parameters to disk.
        """
        if not new_texts:
            return

        logger.info(f"Fitting BM25 model with {len(new_texts)} new document chunks...")

        # Load existing corpus of chunks
        all_texts = []
        if self.chunks_file.exists():
            try:
                with open(self.chunks_file, "r", encoding="utf-8") as f:
                    all_texts = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load existing chunks file: {e}")

        # Append and save the updated corpus
        all_texts.extend(new_texts)
        try:
            self.chunks_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.chunks_file, "w", encoding="utf-8") as f:
                json.dump(all_texts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save chunks file: {e}")

        # Tokenize full corpus
        tokenized_corpus = [self.tokenize(text) for text in all_texts]
        
        # Fit rank_bm25 BM25Okapi model
        bm25 = BM25Okapi(tokenized_corpus, k1=self.k1, b=self.b)

        # Update in-memory params and persist to disk
        self.avgdl = bm25.avgdl
        self.idf = bm25.idf
        self.doc_count = len(tokenized_corpus)
        self.save_model()

    def get_query_sparse_vectors(self, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Generates sparse vectors for query strings.
        Values represent the BM25 IDF scores of query terms.
        """
        sparse_vectors = []
        for query in queries:
            tokens = self.tokenize(query)
            if not tokens:
                sparse_vectors.append({"indices": [], "values": []})
                continue

            # Compute term frequencies in query
            counts = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1

            indices = []
            values = []
            for token, q_tf in counts.items():
                # Hash token to a stable index
                h = hashlib.sha256(token.encode("utf-8")).hexdigest()
                idx = int(h, 16) % self.vocab_size

                # Look up IDF from the rank_bm25 model parameters
                # Default to a small weight if the token was never seen during fit
                idf_val = self.idf.get(token, 1.0)
                # Query term weight = TF * IDF
                weight = q_tf * max(idf_val, 0.0)

                indices.append(idx)
                values.append(float(weight))

            # Pinecone expects sorted indices
            sorted_pairs = sorted(zip(indices, values))
            sorted_indices = [p[0] for p in sorted_pairs]
            sorted_values = [p[1] for p in sorted_pairs]

            sparse_vectors.append({"indices": sorted_indices, "values": sorted_values})

        return sparse_vectors

    def get_document_sparse_vectors(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Generates sparse vectors for document chunks.
        Values represent the BM25 term weights for document terms.
        """
        sparse_vectors = []
        for text in texts:
            tokens = self.tokenize(text)
            if not tokens:
                sparse_vectors.append({"indices": [], "values": []})
                continue

            doc_len = len(tokens)
            counts = {}
            for t in tokens:
                counts[t] = counts.get(t, 0) + 1

            indices = []
            values = []
            for token, f_td in counts.items():
                # Hash token to a stable index
                h = hashlib.sha256(token.encode("utf-8")).hexdigest()
                idx = int(h, 16) % self.vocab_size

                # BM25 document term weight: f_td * (k1 + 1) / (f_td + k1 * (1 - b + b * doc_len / avgdl))
                denom = f_td + self.k1 * (1.0 - self.b + self.b * (doc_len / max(self.avgdl, 1.0)))
                doc_weight = (f_td * (self.k1 + 1.0)) / denom

                indices.append(idx)
                values.append(float(doc_weight))

            # Pinecone expects sorted indices
            sorted_pairs = sorted(zip(indices, values))
            sorted_indices = [p[0] for p in sorted_pairs]
            sorted_values = [p[1] for p in sorted_pairs]

            sparse_vectors.append({"indices": sorted_indices, "values": sorted_values})

        return sparse_vectors


bm25_service = BM25Service()
