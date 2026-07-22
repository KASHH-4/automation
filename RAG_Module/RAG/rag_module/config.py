"""
config.py
---------
Central configuration for the RAG module.

All paths, model names, and tunable hyperparameters live here.
Other modules import from this file — nothing is hardcoded elsewhere.

To switch data sources without touching any other file:
    DATA_SOURCE_TYPE = "json"   →  reads clean_data.json (default)
    DATA_SOURCE_TYPE = "pdf"    →  reads PDFs from PDF_DIR  (legacy fallback)
"""

import os

# ── Directory roots ────────────────────────────────────────────────────────────

# Absolute path to this config file's own directory  (i.e. rag_module/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Parent of rag_module/ — the overall project root
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# ── Data source selection ──────────────────────────────────────────────────────

# Controls which loader is used.
#   "json"  →  load cleaned structured dataset produced by 04_clean_validate.ipynb
#   "pdf"   →  load raw PDF files from PDF_DIR  (legacy behaviour)
# Change ONLY this value to switch — no code edits required.
DATA_SOURCE_TYPE = "json"   # "json" | "pdf"

# ── JSON source (primary pipeline) ────────────────────────────────────────────

# Full path to the cleaned JSON file output by 04_clean_validate.ipynb.
#
# The notebook writes:   <Google Drive>/project/output/clean_data.json
# After syncing locally, place it at:  rag_module/data/clean_data.json
#
# Override at runtime with the environment variable RAG_JSON_PATH, e.g.:
#   export RAG_JSON_PATH="/path/to/your/clean_data.json"
JSON_PATH = os.environ.get(
    "RAG_JSON_PATH",
    os.path.join(BASE_DIR, "data", "clean_data.json"),
)

# Key inside clean_data.json that holds the list of quotation records.
# clean_data.json is a nested dict:
#   { "quotations": [...], "supplier_prices": [...], "exchange_rates": [...], "metadata": {...} }
# The RAG module only indexes the "quotations" list.
JSON_KEY = "quotations"

# ── PDF source (legacy fallback) ───────────────────────────────────────────────

# Folder that contains raw PDF files when DATA_SOURCE_TYPE="pdf".
# Legacy sample PDFs have been moved to sample_data/ and are no longer
# part of the active pipeline.
PDF_DIR = os.path.join(BASE_DIR, "data")

# Kept as DATA_DIR for backward compatibility with any external scripts
# that import it directly.
DATA_DIR = PDF_DIR

# ── FAISS vector store ─────────────────────────────────────────────────────────

# Folder where the FAISS index files are saved and loaded from.
VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")

# FAISS_INDEX_PATH is the folder argument passed to save_local() / load_local().
# LangChain writes two sibling files inside this folder:
#   <FAISS_INDEX_PATH>/index.faiss   ←  binary FAISS index (vectors)
#   <FAISS_INDEX_PATH>/index.pkl     ←  docstore + metadata
# build_index.py and retriever.py must use EXACTLY this value.
FAISS_INDEX_PATH = VECTOR_STORE_DIR

# Stem name for the FAISS file pair produced by save_local() / load_local().
# Default "index" produces  index.faiss  +  index.pkl.
FAISS_INDEX_NAME = "index"

# ── Embedding model ────────────────────────────────────────────────────────────

# Sentence-Transformers model used to embed document chunks and queries.
# "all-MiniLM-L6-v2" is a lightweight, high-quality 384-dim model.
# To upgrade, change only this string and rebuild the index.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# ── Text splitting ─────────────────────────────────────────────────────────────

# Maximum number of characters per chunk fed to the embedding model.
CHUNK_SIZE = 800

# Characters of overlap between consecutive chunks.
# Overlap preserves context at chunk boundaries.
CHUNK_OVERLAP = 150

# ── Retrieval ──────────────────────────────────────────────────────────────────

# Default number of top results returned by retrieve_similar_quotes().
# The caller can override this value at runtime.
DEFAULT_TOP_K = 3
