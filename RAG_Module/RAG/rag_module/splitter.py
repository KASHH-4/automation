"""
splitter.py
-----------
Responsible for splitting raw Document pages into smaller, overlapping chunks.

Pipeline position:  loader.py  →  [splitter.py]  →  embeddings.py
Input:              List of Document objects (one per PDF page)
Output:             List of Document objects (one per text chunk)

Why chunking matters:
  - Embedding models work best on focused, short passages (~200-800 chars).
  - Chunking a full page gives a blurry embedding that matches nothing well.
  - Overlap (150 chars) prevents losing context at chunk boundaries.
"""

from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_SIZE, CHUNK_OVERLAP


def split_documents(documents: List[Document]) -> List[Document]:
    """
    Split a list of LangChain Documents into smaller, overlapping text chunks.

    The splitter tries separators in this priority order:
        1.  "\\n\\n"  — paragraph break (best split point)
        2.  "\\n"     — line break
        3.  ". "      — end of sentence
        4.  " "       — word boundary (last resort)
        5.  ""        — character-level (never ideal, but safe fallback)

    Each output chunk inherits the full metadata of its parent Document
    (source path, page number, file_name) so provenance is never lost.

    Args:
        documents: Flat list of Document objects produced by loader.load_pdfs().

    Returns:
        Flat list of Document chunks ready for embedding.
        Returns an empty list if the input is empty.
    """

    if not documents:
        print("[splitter] ⚠  No documents provided. Returning empty list.")
        return []

    # ── Build the splitter ────────────────────────────────────────────────────
    # chunk_size    : max characters per chunk (set in config.py → 800)
    # chunk_overlap : characters shared between consecutive chunks (→ 150)
    # add_start_index: stores char offset in metadata — useful for debugging
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,           # metadata["start_index"] = char offset
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    # ── Split all documents in one call ───────────────────────────────────────
    # split_documents() handles the loop internally and copies metadata to
    # every child chunk automatically — no manual metadata propagation needed.
    chunks = splitter.split_documents(documents)

    print(f"[splitter] {len(documents)} page(s)  →  {len(chunks)} chunk(s)  "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    return chunks


def log_chunk_stats(chunks: List[Document]) -> None:
    """
    Optional helper — prints per-file chunk counts and average chunk size.
    Useful during development to verify the split quality.

    Args:
        chunks: Output of split_documents().
    """
    if not chunks:
        print("[splitter] No chunks to inspect.")
        return

    from collections import defaultdict

    file_counts: dict = defaultdict(int)
    total_chars = 0

    for chunk in chunks:
        fname = chunk.metadata.get("file_name", "unknown")
        file_counts[fname] += 1
        total_chars += len(chunk.page_content)

    avg_size = total_chars // len(chunks)

    print("\n── Chunk statistics ──────────────────────────────────────")
    for fname, count in sorted(file_counts.items()):
        print(f"  {fname:40s}  {count:>4d} chunk(s)")
    print(f"  {'Average chunk size':40s}  {avg_size:>4d} chars")
    print("──────────────────────────────────────────────────────────\n")


# ── Quick smoke-test ──────────────────────────────────────────────────────────
# Run directly to verify splitting works independently of the full pipeline.
#   python splitter.py
if __name__ == "__main__":
    from loader import load_pdfs

    raw_docs = load_pdfs()
    chunks = split_documents(raw_docs)

    if chunks:
        log_chunk_stats(chunks)
        print("── Sample chunk (first) ──")
        print(f"File       : {chunks[0].metadata.get('file_name')}")
        print(f"Page       : {chunks[0].metadata.get('page')}")
        print(f"Start index: {chunks[0].metadata.get('start_index')}")
        print(f"Length     : {len(chunks[0].page_content)} chars")
        print(f"Preview    :\n{chunks[0].page_content[:300]}")
