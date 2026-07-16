# import os
# import sys
# import asyncio
# from pathlib import Path
# from typing import Any, List
# import httpx

# # Add workspace directory to python path
# workspace_dir = str(Path(__file__).resolve().parents[3])
# if workspace_dir not in sys.path:
#     sys.path.insert(0, workspace_dir)

# from src.app.core.config import settings
# from llama_index.core import Document
# from llama_index.core.node_parser import HierarchicalNodeParser, SemanticSplitterNodeParser, SentenceSplitter
# from llama_index.core.embeddings import BaseEmbedding
# from llama_index.core.bridge.pydantic import PrivateAttr

# # Define custom Jina Embedding wrapper for LlamaIndex
# class JinaEmbedding(BaseEmbedding):
#     _api_key: str = PrivateAttr()
#     _api_url: str = PrivateAttr()

#     def __init__(self, api_key: str, model_name: str = "jina-embeddings-v3", **kwargs: Any) -> None:
#         super().__init__(model_name=model_name, **kwargs)
#         self._api_key = api_key
#         self._api_url = "https://api.jina.ai/v1/embeddings"

#     @classmethod
#     def class_name(cls) -> str:
#         return "JinaEmbedding"

#     def _get_query_embedding(self, query: str) -> List[float]:
#         return self._get_text_embeddings([query])[0]

#     def _get_text_embedding(self, text: str) -> List[float]:
#         return self._get_text_embeddings([text])[0]

#     def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
#         headers = {
#             "Authorization": f"Bearer {self._api_key}",
#             "Content-Type": "application/json"
#         }
#         payload = {
#             "model": self.model_name,
#             "input": texts,
#             "dimensions": 1024
#         }
#         with httpx.Client(timeout=60.0) as client:
#             response = client.post(self._api_url, headers=headers, json=payload)
#             if response.status_code == 200:
#                 res_json = response.json()
#                 return [item["embedding"] for item in res_json.get("data", [])]
#             else:
#                 raise RuntimeError(f"Jina API request failed: {response.status_code} - {response.text}")

#     async def _aget_query_embedding(self, query: str) -> List[float]:
#         return (await self._aget_text_embeddings([query]))[0]

#     async def _aget_text_embedding(self, text: str) -> List[float]:
#         return (await self._aget_text_embeddings([text]))[0]

#     async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
#         headers = {
#             "Authorization": f"Bearer {self._api_key}",
#             "Content-Type": "application/json"
#         }
#         payload = {
#             "model": self.model_name,
#             "input": texts,
#             "dimensions": 1024
#         }
#         async with httpx.AsyncClient(timeout=60.0) as client:
#             response = await client.post(self._api_url, headers=headers, json=payload)
#             if response.status_code == 200:
#                 res_json = response.json()
#                 return [item["embedding"] for item in res_json.get("data", [])]
#             else:
#                 raise RuntimeError(f"Jina API request failed: {response.status_code} - {response.text}")


# async def run_experiment():
#     print("=" * 80)
#     print("JINA EMBEDDINGS + LLAMAINDEX HIERARCHICAL & SEMANTIC CHUNKING EXPERIMENT")
#     print("=" * 80)

#     # 1. Ensure API key is loaded
#     api_key = settings.JINA_API_KEY
#     if not api_key:
#         print("[!] Error: JINA_API_KEY is not configured in .env!")
#         return

#     print(f"[+] Loaded Jina API Key (starts with: {api_key[:8]}...)")

#     # 2. Load the sample markdown file (demo.md)
#     demo_file_path = Path(__file__).resolve().parent / "demo.md"
#     if not demo_file_path.exists():
#         print(f"[!] Error: Could not find demo.md at {demo_file_path}")
#         return

#     with open(demo_file_path, "r", encoding="utf-8") as f:
#         markdown_content = f.read()

#     doc = Document(text=markdown_content, id_="demo_doc")
#     print(f"[+] Loaded demo.md ({len(markdown_content)} characters)")

#     # 3. Instantiate Jina embedding model
#     embed_model = JinaEmbedding(api_key=api_key)

#     # 4. Set up SemanticSplitterNodeParser
#     print("\n[~] Initializing SemanticSplitterNodeParser with Jina Embeddings...")
#     semantic_splitter = SemanticSplitterNodeParser(
#         buffer_size=1,
#         breakpoint_percentile_threshold=90,
#         embed_model=embed_model
#     )

#     # 5. Set up HierarchicalNodeParser combining Semantic + Hierarchical splitting
#     # Level 1 (Parent): Semantic chunks
#     # Level 2 (Child): Sentence-level chunks (using a smaller threshold/buffer or SentenceSplitter)
#     print("[~] Configuring HierarchicalNodeParser with custom node parser map...")
#     node_parser_map = {
#         "parent_semantic": semantic_splitter,
#         "child_sentence": SentenceSplitter(chunk_size=150, chunk_overlap=20)
#     }
#     node_parser_ids = ["parent_semantic", "child_sentence"]

#     hierarchical_parser = HierarchicalNodeParser(
#         node_parser_ids=node_parser_ids,
#         node_parser_map=node_parser_map
#     )

#     # 6. Parse document
#     print("[~] Running HierarchicalNodeParser on the document...")
#     try:
#         nodes = hierarchical_parser.get_nodes_from_documents([doc])
#         print(f"[+] Parsing complete! Generated {len(nodes)} total nodes.\n")

#         # Separate parent and child nodes
#         # In LlamaIndex, child nodes contain metadata references to parent nodes ('parent_ref')
#         # or parent nodes contain references to children.
#         # Let's inspect the hierarchy relations.
#         parent_nodes = []
#         child_nodes = []

#         for node in nodes:
#             # Check relations
#             parent_ref = node.parent_node
#             child_refs = node.child_nodes

#             if parent_ref is None:
#                 parent_nodes.append(node)
#             else:
#                 child_nodes.append(node)

#         print(f"--- RESULTS SUMMARY ---")
#         print(f"Total Parent Nodes (Semantic Sections): {len(parent_nodes)}")
#         print(f"Total Child Nodes (Finer chunks):       {len(child_nodes)}")
#         print("-" * 40)

#         print("\n>>> PARENT NODES (SEMANTIC SECTIONS):")
#         for idx, p_node in enumerate(parent_nodes):
#             print(f"\nParent {idx+1} [ID: {p_node.node_id}]:")
#             preview = p_node.text.strip().replace('\n', ' ')
#             print(f"  Text preview: {preview[:120]}...")
#             print(f"  Children IDs: {[c.node_id for c in p_node.child_nodes] if p_node.child_nodes else []}")

#         print("\n>>> CHILD NODES MAP:")
#         for idx, c_node in enumerate(child_nodes):
#             p_ref_id = c_node.parent_node.node_id if c_node.parent_node else "None"
#             print(f"  Child {idx+1} [ID: {c_node.node_id}] -> Parent ID: {p_ref_id}")
#             preview = c_node.text.strip().replace('\n', ' ')
#             print(f"    Text: {preview[:100]}...")

#     except Exception as e:
#         print(f"[!] Error during parsing experiment: {e}")
#         import traceback
#         traceback.print_exc()

# if __name__ == "__main__":
#     asyncio.run(run_experiment())
