"""
build_index.py
--------------
Orchestrates the full ingestion pipeline and persists the FAISS vector index.

# [UPDATED] Pipeline now starts from the cleaned structured dataset produced
# by 04_clean_validate.ipynb (when DATA_SOURCE_TYPE="json" in config.py).
# Set DATA_SOURCE_TYPE="pdf" to restore the original PDF behaviour.
#
Pipeline:  cleaned dataset  →  loader  →  splitter  →  embeddings  →  FAISS  →  disk

Run this script ONCE (or whenever PDFs change) to build / rebuild the index.
The retriever.py module then loads this pre-built index at query time — no
re-embedding needed for every query.

Usage:
    python build_index.py

Expected output files:
    vector_store/index.faiss   ← compressed FAISS index (the actual vectors)
    vector_store/index.pkl     ← metadata / docstore (page content + metadata)
"""

import os
import sys

from langchain_community.vectorstores import FAISS

from config import VECTOR_STORE_DIR, FAISS_INDEX_PATH, FAISS_INDEX_NAME
# [UPDATED] Import load_documents (dispatcher) instead of load_pdfs.
# load_documents() reads DATA_SOURCE_TYPE from config and routes accordingly.
from loader import load_documents
from splitter import split_documents, log_chunk_stats
from embeddings import get_embedding_model


def build_faiss_index() -> None:
    """
    Full ingestion pipeline:
      1. Load all PDFs from data/
      2. Split pages into overlapping chunks
      3. Embed every chunk using the Sentence Transformer model
      4. Build a FAISS index from those embeddings
      5. Save the index to vector_store/

    Raises:
        SystemExit if no documents are found (nothing to index).
    """

    print("\n" + "=" * 60)
    print("  AI Proposal Intelligence — RAG Index Builder")
    print("=" * 60 + "\n")

    # ── Step 1: Load documents ───────────────────────────────────────────────
    # [UPDATED] load_documents() dispatches to JSON or PDF based on config.
    print("Step 1/4  Loading documents...")
    documents = load_documents()

    if not documents:
        print("\n[build_index] ✖  No documents loaded. "
              "Check DATA_SOURCE_TYPE and JSON_PATH (or DATA_DIR for PDF) in config.py.")
        sys.exit(1)

    # ── Step 2: Split into chunks ─────────────────────────────────────────────
    print("\nStep 2/4  Splitting documents into chunks...")
    chunks = split_documents(documents)
    log_chunk_stats(chunks)          # optional stats printout

    if not chunks:
        print("[build_index] ✖  Splitting produced no chunks. Aborting.")
        sys.exit(1)

    # ── Step 3: Load embedding model ──────────────────────────────────────────
    print("Step 3/4  Loading embedding model...")
    embedding_model = get_embedding_model()

    # ── Step 4: Build FAISS index and save ───────────────────────────────────
    print("\nStep 4/4  Building FAISS vector index...")
    print(f"          Embedding {len(chunks)} chunks — this may take a moment...")

    # FAISS.from_documents():
    #   - Calls embedding_model.embed_documents() on all chunk texts in one batch
    #   - Builds an IndexFlatL2 FAISS index internally
    #   - Stores (vector, Document) pairs so we can retrieve full text + metadata
    vector_store = FAISS.from_documents(
        documents=chunks,
        embedding=embedding_model,
    )

    # Ensure the output directory exists before saving
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

    # save_local(folder_path, index_name) writes two sibling files:
    #   <FAISS_INDEX_PATH>/index.faiss  — binary FAISS index (vectors)
    #   <FAISS_INDEX_PATH>/index.pkl    — Python pickle of the docstore + metadata
    # FAISS_INDEX_PATH  = vector_store/   (the folder)
    # FAISS_INDEX_NAME  = "index"          (the file stem)
    vector_store.save_local(FAISS_INDEX_PATH, FAISS_INDEX_NAME)

    faiss_file = os.path.join(FAISS_INDEX_PATH, f"{FAISS_INDEX_NAME}.faiss")
    pkl_file   = os.path.join(FAISS_INDEX_PATH, f"{FAISS_INDEX_NAME}.pkl")

    print(f"\n[build_index] ✔  Index saved to folder: {FAISS_INDEX_PATH}")
    print(f"              Files created:")
    print(f"                {faiss_file}")
    print(f"                {pkl_file}")
    print("\n" + "=" * 60)
    print("  Index build complete. Run retriever.py to test queries.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    build_faiss_index()
