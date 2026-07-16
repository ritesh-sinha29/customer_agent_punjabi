import logging
import re
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger("ChunkingService")


class ChunkingService:
    """
    Handles Step 3: Chunking (Semantic + Structure-Aware + Hierarchical).
    """

    def __init__(self):
        self._embedding_model = None

    def _get_embedding_model(self):
        """
        Lazy-loads a local sentence transformer model for semantic chunking.
        Uses a lightweight model that runs quickly.
        """
        if self._embedding_model is None:
            logger.info(
                "Initializing SentenceTransformer (all-MiniLM-L6-v2) for Semantic Chunking..."
            )
            try:
                from sentence_transformers import SentenceTransformer

                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("SentenceTransformer model loaded successfully.")
            except ImportError:
                logger.error(
                    "sentence-transformers is not installed. Semantic chunking will fall back to recursive chunking."
                )
                raise ImportError(
                    "Please install 'sentence-transformers' to use semantic chunking."
                )
        return self._embedding_model

    def split_text_recursive(
        self, text: str, max_chars: int = 1500, overlap_chars: int = 200
    ) -> List[str]:
        """
        Standard recursive text splitter helper. Splits text by paragraphs, sentences, and words.
        """
        if len(text) <= max_chars:
            return [text]

        # Order of separators to try
        separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

        # Find the best separator
        separator = separators[-1]
        for sep in separators:
            if sep in text:
                separator = sep
                break

        chunks = []
        if separator == "":
            # Hard limit split if no separator is found
            for i in range(0, len(text), max_chars - overlap_chars):
                chunks.append(text[i : i + max_chars])
            return chunks

        # Split by the separator
        splits = text.split(separator)
        current_chunk = []
        current_length = 0

        for split in splits:
            # Reconstruct the string
            item = split + separator if split != splits[-1] else split
            item_len = len(item)

            if current_length + item_len > max_chars:
                if current_chunk:
                    chunks.append("".join(current_chunk))

                    # Keep overlap: find how many previous splits we can fit within the overlap limit
                    overlap_chunk = []
                    overlap_len = 0
                    for prev_split in reversed(current_chunk):
                        if overlap_len + len(prev_split) <= overlap_chars:
                            overlap_chunk.insert(0, prev_split)
                            overlap_len += len(prev_split)
                        else:
                            break
                    current_chunk = overlap_chunk
                    current_length = overlap_len

                # If a single item is larger than max_chars, split it recursively
                if item_len > max_chars:
                    sub_chunks = self.split_text_recursive(
                        item, max_chars, overlap_chars
                    )
                    chunks.extend(sub_chunks[:-1])
                    if sub_chunks:
                        current_chunk.append(sub_chunks[-1])
                        current_length = len(sub_chunks[-1])
                else:
                    current_chunk.append(item)
                    current_length = item_len
            else:
                current_chunk.append(item)
                current_length += item_len

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    def chunk_by_structure(
        self,
        markdown_text: str,
        doc_id: str,
        max_chars: int = 1500,
        overlap_chars: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Structure-Aware Chunking:
        - Splits markdown by headings (# Header 1, ## Header 2, etc.)
        - Tracks active heading path hierarchy (headings_path)
        - Sub-splits text blocks recursively to fit within max_chars
        - Returns chunks with complete metadata
        """
        logger.info("[Step 3 - Structure-Aware] Starting markdown structural split...")
        lines = markdown_text.split("\n")

        # Keep track of the active headers stack
        # headers_stack[level] = header_text
        headers_stack = {}
        current_section_text = []
        chunks = []
        chunk_index = 0

        def get_current_headings_path() -> List[str]:
            # Sort headers by level and return the list of header texts
            sorted_levels = sorted(headers_stack.keys())
            return [headers_stack[lvl] for lvl in sorted_levels]

        def process_current_section():
            nonlocal chunk_index
            section_content = "\n".join(current_section_text).strip()
            if not section_content:
                return

            path = get_current_headings_path()
            headings_path_str = " > ".join(path) if path else "Root"

            # If section content is too large, split it recursively
            sub_splits = self.split_text_recursive(
                section_content, max_chars, overlap_chars
            )

            for sub_text in sub_splits:
                if not sub_text.strip():
                    continue

                chunk_id = f"{doc_id}#c{chunk_index}"
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "text": sub_text,
                        "headings_path": path,
                        "headings_path_str": headings_path_str,
                        "metadata": {
                            "chunk_index": chunk_index,
                            "headings_path": path,
                            "headings_path_str": headings_path_str,
                            "type": "structure_aware",
                        },
                    }
                )
                chunk_index += 1

        heading_regex = re.compile(r"^(#{1,6})\s+(.*)$")

        for line in lines:
            match = heading_regex.match(line)
            if match:
                # Heading matched
                # First, process and save the accumulated section text under the previous headers
                process_current_section()
                current_section_text = []

                hashes, heading_text = match.groups()
                level = len(hashes)
                heading_text = heading_text.strip()

                # Clean up higher or equal level headings from the stack
                levels_to_remove = [lvl for lvl in headers_stack.keys() if lvl >= level]
                for lvl in levels_to_remove:
                    del headers_stack[lvl]

                # Update current heading level
                headers_stack[level] = heading_text

                # We also include the heading line in the text of the new section
                current_section_text.append(line)
            else:
                current_section_text.append(line)

        # Process any remaining text
        process_current_section()

        logger.info(
            f"[Step 3 - Structure-Aware] Generated {len(chunks)} structure-aware chunks."
        )
        return chunks

    def chunk_semantically(
        self,
        text: str,
        doc_id: str,
        similarity_threshold: float = 0.8,
        min_chunk_size_chars: int = 300,
        max_chunk_size_chars: int = 1500,
    ) -> List[Dict[str, Any]]:
        """
        Semantic Chunking:
        - Splits document into sentences
        - Groups sentences into semantic blocks using local embeddings
        - Splits on similarity drops below similarity_threshold
        """
        logger.info("[Step 3 - Semantic] Starting semantic embedding-based split...")

        # Simple sentence splitter
        sentence_ends = re.compile(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s")
        sentences = [s.strip() for s in sentence_ends.split(text) if s.strip()]

        if not sentences:
            return []

        try:
            model = self._get_embedding_model()
        except Exception as e:
            logger.warning(
                f"Could not load embedding model: {e}. Falling back to structure-aware/recursive."
            )
            # Fallback to simple recursive splitting
            chunks = []
            sub_splits = self.split_text_recursive(text, max_chunk_size_chars, 200)
            for idx, sub_text in enumerate(sub_splits):
                chunks.append(
                    {
                        "chunk_id": f"{doc_id}#c{idx}",
                        "doc_id": doc_id,
                        "text": sub_text,
                        "headings_path": [],
                        "headings_path_str": "Root",
                        "metadata": {"chunk_index": idx, "type": "fallback_recursive"},
                    }
                )
            return chunks

        # Compute embeddings for sentences
        logger.info(f"[Step 3 - Semantic] Encoding {len(sentences)} sentences...")
        embeddings = model.encode(sentences, convert_to_numpy=True)

        # Compute cosine similarities between consecutive sentences
        similarities = []
        for i in range(len(embeddings) - 1):
            emb_i = embeddings[i]
            emb_next = embeddings[i + 1]

            norm_i = np.linalg.norm(emb_i)
            norm_next = np.linalg.norm(emb_next)

            if norm_i > 0 and norm_next > 0:
                sim = np.dot(emb_i, emb_next) / (norm_i * norm_next)
            else:
                sim = 0.0
            similarities.append(sim)

        # Determine split indices based on similarity drop
        chunks = []
        current_chunk_sentences = []
        current_chunk_chars = 0
        chunk_index = 0

        for idx, sentence in enumerate(sentences):
            current_chunk_sentences.append(sentence)
            current_chunk_chars += len(sentence)

            # Check if we should split
            should_split = False

            # If we're at the last sentence, we must split
            if idx == len(sentences) - 1:
                should_split = True
            else:
                sim = similarities[idx]

                # Check similarity threshold and constraints
                if sim < similarity_threshold:
                    # Only split if the current chunk is not too small, unless it's already too large
                    if current_chunk_chars >= min_chunk_size_chars:
                        should_split = True

                # Hard ceiling check
                if current_chunk_chars >= max_chunk_size_chars:
                    should_split = True

            if should_split:
                chunk_text = " ".join(current_chunk_sentences)
                chunk_id = f"{doc_id}#c{chunk_index}"

                # Log similarity info for console visibility
                sim_value = similarities[idx - 1] if idx > 0 else 1.0
                logger.debug(
                    f"Creating semantic chunk {chunk_index} (sim drop to {sim_value:.3f})"
                )

                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "text": chunk_text,
                        "headings_path": [],
                        "headings_path_str": "Semantic Split",
                        "metadata": {
                            "chunk_index": chunk_index,
                            "type": "semantic",
                            "sentences_count": len(current_chunk_sentences),
                            "split_similarity": float(sim_value),
                        },
                    }
                )

                # Reset for next chunk
                current_chunk_sentences = []
                current_chunk_chars = 0
                chunk_index += 1

        logger.info(f"[Step 3 - Semantic] Generated {len(chunks)} semantic chunks.")
        return chunks

    def chunk_hierarchical(
        self,
        markdown_text: str,
        doc_id: str,
        parent_max_chars: int = 3000,
        child_max_chars: int = 800,
        similarity_threshold: float = 0.8,
    ) -> Dict[str, Any]:
        """
        Combined Semantic & Hierarchical Parent-Child Chunking:
        1. Parent chunks are created based on document headings (structural sections).
        2. Child chunks within each parent section are created semantically based on sentence similarity drops.
        3. Establishes relational mapping (parent_id on child chunks).
        """
        logger.info(
            "[Step 3 - Combined Semantic-Hierarchical] Starting parent-child split..."
        )

        # 1. Generate parent chunks by structure (using a larger character limit)
        parent_chunks = self.chunk_by_structure(
            markdown_text=markdown_text,
            doc_id=doc_id,
            max_chars=parent_max_chars,
            overlap_chars=parent_max_chars // 10,
        )

        child_chunks = []
        child_index = 0

        # 2. For each parent chunk, split it into semantic child chunks
        for p_chunk in parent_chunks:
            p_id = p_chunk["chunk_id"]
            p_text = p_chunk["text"]

            # Split parent text semantically using sentence embeddings
            semantic_splits = self.chunk_semantically(
                text=p_text,
                doc_id=doc_id,
                similarity_threshold=similarity_threshold,
                max_chunk_size_chars=child_max_chars,
            )

            p_child_ids = []
            for sem_chunk in semantic_splits:
                sub_text = sem_chunk["text"]
                if not sub_text.strip():
                    continue

                c_id = f"{doc_id}#child{child_index}"
                p_child_ids.append(c_id)

                child_chunks.append(
                    {
                        "chunk_id": c_id,
                        "parent_id": p_id,
                        "doc_id": doc_id,
                        "text": sub_text,
                        "headings_path": p_chunk["headings_path"],
                        "headings_path_str": p_chunk["headings_path_str"],
                        "metadata": {
                            "child_index": child_index,
                            "parent_id": p_id,
                            "type": "hierarchical_child",
                            "sentences_count": sem_chunk["metadata"].get(
                                "sentences_count", 0
                            ),
                            "split_similarity": sem_chunk["metadata"].get(
                                "split_similarity", 1.0
                            ),
                        },
                    }
                )
                child_index += 1

            # Add child references to the parent metadata
            p_chunk["metadata"]["child_ids"] = p_child_ids
            p_chunk["metadata"]["type"] = "hierarchical_parent"

        logger.info(
            f"[Step 3 - Combined Semantic-Hierarchical] Generated {len(parent_chunks)} parent chunks and {len(child_chunks)} child chunks."
        )
        return {"parent_chunks": parent_chunks, "child_chunks": child_chunks}


chunking_service = ChunkingService()
