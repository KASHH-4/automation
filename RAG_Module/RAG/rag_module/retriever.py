"""
retriever.py
------------
Public interface for the RAG module.

This is the ONLY file your teammate's proposal generation system needs to import.

Pipeline position:  vector_store/  →  [retriever.py]  →  proposal generator

Exposes:
    retrieve_similar_quotes(query: str, k: int = 3) → List[dict]

Usage example:
    from retriever import retrieve_similar_quotes

    results = retrieve_similar_quotes("steel beam quotation for 500 units", k=3)
    for r in results:
        print(r["quotation_id"], r["customer"], r["similarity_score"])
        print(r["content"])
        print(r["metadata"])
"""

import os
from typing import List, Dict, Any

from langchain_community.vectorstores import FAISS

from config import FAISS_INDEX_PATH, FAISS_INDEX_NAME, DEFAULT_TOP_K
from embeddings import get_embedding_model


# ── Module-level cache ────────────────────────────────────────────────────────
# The FAISS index is loaded once and reused for every query in the same session.
# This avoids expensive disk I/O and re-loading model weights on every call.
_vector_store: FAISS | None = None


def _load_vector_store() -> FAISS:
    """
    Load the FAISS index from disk (once) and cache it in module memory.

    Returns:
        Loaded FAISS vector store.

    Raises:
        FileNotFoundError: if the index files don't exist yet.
                           Run build_index.py first.
    """
    global _vector_store

    # Return cached instance if already loaded
    if _vector_store is not None:
        return _vector_store

    # Validate that the index files exist before attempting to load
    faiss_file = os.path.join(FAISS_INDEX_PATH, f"{FAISS_INDEX_NAME}.faiss")
    pkl_file   = os.path.join(FAISS_INDEX_PATH, f"{FAISS_INDEX_NAME}.pkl")

    if not os.path.exists(faiss_file) or not os.path.exists(pkl_file):
        raise FileNotFoundError(
            f"[retriever] FAISS index not found.\n"
            f"  Expected: {faiss_file}\n"
            f"            {pkl_file}\n"
            "Please run:  python build_index.py"
        )

    print("[retriever] Loading FAISS index from disk...")
    embedding_model = get_embedding_model()

    # allow_dangerous_deserialization=True is required when loading a .pkl file.
    # This is safe here because WE wrote the pickle in build_index.py.
    _vector_store = FAISS.load_local(
        folder_path=FAISS_INDEX_PATH,
        embeddings=embedding_model,
        index_name=FAISS_INDEX_NAME,
        allow_dangerous_deserialization=True,
    )

    print("[retriever] ✔ FAISS index loaded.")
    return _vector_store


def retrieve_similar_quotes(
    query: str,
    k: int = DEFAULT_TOP_K,
) -> List[Dict[str, Any]]:
    """
    Retrieve the top-K most semantically similar quotation chunks for a query.

    How it works:
      1. The query string is embedded using the same model used at index time.
      2. FAISS performs an approximate nearest-neighbour (ANN) search in vector space.
      3. The k closest document chunks are returned, ranked by similarity.

    Args:
        query : Natural-language question or description, e.g.
                "steel beam quotation for 500 units, 14-day delivery".
        k     : Number of results to return (default: DEFAULT_TOP_K from config).

    Returns:
        List of dicts, each containing:
            {
                # ── Quotation identity fields (from Document metadata) ─────────
                "quotation_id"     : str,   # [NEW] e.g. "Q-2024-001"
                "customer"         : str,   # [NEW] e.g. "Acme Corp"
                "supplier"         : str,   # [NEW] e.g. "SteelCo Ltd"
                "currency"         : str,   # [NEW] e.g. "USD"
                "source_file"      : str,   # [NEW] originating file/record ref
                # ── Legacy fields (kept for backward compatibility) ──────────
                "file_name"        : str,   # source filename (same as source_file)
                # ── Retrieval fields ─────────────────────────────────────
                "content"          : str,   # matching text chunk
                "similarity_score" : float, # 0.0 (no match) → 1.0 (perfect)
                # ── Full raw metadata ──────────────────────────────────────
                "metadata"         : dict,  # [NEW] complete doc.metadata dict
            }
        Sorted by similarity_score descending (best match first).

    Raises:
        FileNotFoundError : if the index hasn't been built yet.
        ValueError        : if query is empty or k < 1.
    """

    # ── Input validation ──────────────────────────────────────────────────────
    if not query or not query.strip():
        raise ValueError("[retriever] Query string cannot be empty.")
    if k < 1:
        raise ValueError(f"[retriever] k must be ≥ 1, got {k}.")

    # ── Load index (cached after first call) ──────────────────────────────────
    vector_store = _load_vector_store()

    # ── Similarity search ─────────────────────────────────────────────────────
    # similarity_search_with_score() returns List[Tuple[Document, float]]
    # The float is the L2 distance (lower = more similar).
    # We convert it to a cosine-like score in [0, 1].
    raw_results = vector_store.similarity_search_with_score(query, k=k)

    # ── Format results ────────────────────────────────────────────────────────
    formatted: List[Dict[str, Any]] = []

    for doc, l2_distance in raw_results:
        # Convert L2 distance → similarity score in [0, 1].
        # Formula:  score = 1 / (1 + distance)
        # • distance ≈ 0  →  score ≈ 1.0  (very similar)
        # • distance → ∞  →  score → 0.0  (completely different)
        similarity_score = round(1 / (1 + l2_distance), 4)

        # [UPDATED] Return an enriched dict with all quotation metadata fields.
        # Fields sourced from Document.metadata (populated by loader.load_json).
        # Legacy keys (file_name, content, similarity_score) are kept so any
        # existing code that reads them continues to work without changes.
        formatted.append({
            # ── Quotation identity ────────────────────────────────────
            "quotation_id"     : doc.metadata.get("quotation_id", ""),
            "customer"         : doc.metadata.get("customer", ""),
            "supplier"         : doc.metadata.get("supplier", ""),
            "currency"         : doc.metadata.get("currency", ""),
            "source_file"      : doc.metadata.get("source_file",
                                    doc.metadata.get("file_name", "unknown")),
            # ── Legacy field (backward compat) ───────────────────────────
            "file_name"        : doc.metadata.get("file_name", "unknown"),
            # ── Retrieval fields ──────────────────────────────────────
            "content"          : doc.page_content.strip(),
            "similarity_score" : similarity_score,
            # ── Full metadata (for LLM prompt assembly, debugging, etc.) ───
            "metadata"         : dict(doc.metadata),   # shallow copy
        })

    # Results from FAISS are already ordered best-first; sort reinforces this.
    formatted.sort(key=lambda x: x["similarity_score"], reverse=True)

    return formatted


# ── Quick smoke-test ──────────────────────────────────────────────────────────
# Run after building the index to verify end-to-end retrieval.
#   python retriever.py
if __name__ == "__main__":
    test_query = "stainless steel quotation with 30-day delivery"
    print(f"\nQuery: '{test_query}'\n")

    try:
        results = retrieve_similar_quotes(test_query, k=3)

        if not results:
            print("No results returned. Ensure the index is built and data is loaded.")
        else:
            for i, r in enumerate(results, 1):
                print(f"── Result {i} ───────────────────────────────────────────────")
                # [UPDATED] Print all enriched fields for easier inspection
                print(f"  Quotation ID : {r['quotation_id']}")
                print(f"  Customer     : {r['customer']}")
                print(f"  Supplier     : {r['supplier']}")
                print(f"  Currency     : {r['currency']}")
                print(f"  Source File  : {r['source_file']}")
                print(f"  Score        : {r['similarity_score']}")
                print(f"  Content      : {r['content'][:250]}")
                print()

    except FileNotFoundError as e:
        print(e)
