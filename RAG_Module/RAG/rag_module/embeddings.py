"""
embeddings.py
-------------
Responsible for loading and exposing the Sentence Transformer embedding model.

Pipeline position:  splitter.py  →  [embeddings.py]  →  build_index.py
Output:             A LangChain-compatible HuggingFaceEmbeddings object

Why a dedicated file?
  - The same embedding object MUST be used during both:
      1. Index building  (build_index.py)   → encodes document chunks
      2. Query time      (retriever.py)     → encodes the user's question
  - Centralising it here guarantees both stages use identical vector spaces.
    If you use different models for indexing vs. querying, all scores are wrong.
"""

from langchain_huggingface import HuggingFaceEmbeddings

from config import EMBEDDING_MODEL_NAME


def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Load and return a LangChain-compatible Sentence Transformer embedding model.

    HuggingFaceEmbeddings is a thin LangChain wrapper around the
    sentence-transformers library. It implements the Embeddings interface,
    so it plugs directly into FAISS.from_documents() and FAISS.load_local().

    Model behaviour:
      - First call: downloads the model weights from HuggingFace Hub (~90 MB).
      - Subsequent calls: loads from local cache instantly.
      - Inference runs on CPU by default; set model_kwargs={"device":"cuda"}
        to enable GPU if available.

    Returns:
        HuggingFaceEmbeddings instance ready for use in build_index / retriever.
    """

    print(f"[embeddings] Loading embedding model: '{EMBEDDING_MODEL_NAME}' ...")

    embedding_model = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,

        # encode_kwargs: passed directly to model.encode()
        # normalize_embeddings=True → unit-length vectors (required for cosine similarity)
        encode_kwargs={"normalize_embeddings": True},
    )

    print("[embeddings] ✔ Embedding model loaded successfully.")
    return embedding_model


# ── Quick smoke-test ──────────────────────────────────────────────────────────
# Run directly to confirm the model downloads and embeds correctly.
#   python embeddings.py
if __name__ == "__main__":
    model = get_embedding_model()

    sample_texts = [
        "Customer: Acme Corp, Product: Steel Beam, Quantity: 500 units",
        "Delivery Time: 14 days, Base Cost: $12,500",
    ]

    vectors = model.embed_documents(sample_texts)
    print(f"\nEmbedded {len(vectors)} texts.")
    print(f"Vector dimensions : {len(vectors[0])}")
    print(f"First vector (preview): {vectors[0][:6]} ...")
