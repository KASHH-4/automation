"""
loader.py
---------
Loads source data and returns a flat list of LangChain Document objects.

Supports two data sources, controlled by DATA_SOURCE_TYPE in config.py:

  "json"  (default) — reads clean_data.json produced by 04_clean_validate.ipynb.
           The file is a nested dict; the "quotations" key (JSON_KEY) holds the
           list of records. Each record becomes one LangChain Document.

  "pdf"   (legacy)  — walks PDF_DIR, loads every PDF, returns one Document
           per page. Original behaviour, fully preserved for fallback use.

Pipeline position:  data source  →  [loader.py]  →  splitter.py
Output:             List[Document]  — page_content + metadata per record
"""

import os
import json
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from config import DATA_DIR, PDF_DIR, DATA_SOURCE_TYPE, JSON_PATH, JSON_KEY


# ── PDF loader (legacy) ────────────────────────────────────────────────────────

def load_pdfs(data_dir: str = PDF_DIR) -> List[Document]:
    """
    Walk *data_dir*, load every PDF found, and return a flat list of
    LangChain Document objects (one Document per page).

    Args:
        data_dir: Folder containing source PDFs. Defaults to PDF_DIR in config.

    Returns:
        Flat list of Document objects. Empty list if no PDFs found or on error.
        Errors are caught per-file so one corrupt PDF cannot abort the run.
    """

    # 1. Validate directory
    if not os.path.exists(data_dir):
        print(f"[loader] ⚠  PDF directory not found: {data_dir}")
        return []

    # 2. Collect PDF paths (case-insensitive extension match)
    pdf_files = [
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.lower().endswith(".pdf")
    ]

    if not pdf_files:
        print(f"[loader] ⚠  No PDF files found in: {data_dir}")
        return []

    print(f"[loader] Found {len(pdf_files)} PDF file(s). Loading...")

    # 3. Load each PDF; accumulate Document objects
    all_documents: List[Document] = []

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)
        try:
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()

            # Enrich metadata with the bare filename for clean display
            for doc in pages:
                doc.metadata["file_name"] = file_name

            all_documents.extend(pages)
            print(f"[loader]   ✔  {file_name}  ({len(pages)} page(s))")

        except Exception as exc:
            # Log but continue — one bad PDF must not abort the run
            print(f"[loader]   ✖  Failed to load '{file_name}': {exc}")

    print(f"[loader] Total pages loaded: {len(all_documents)}")
    return all_documents


# ── JSON loader (primary pipeline) ────────────────────────────────────────────

# Human-readable label map for known quotation field keys.
# Keys absent from this map are auto-formatted as Title Case.
_LABEL_MAP = {
    "quotation_id"    : "Quotation ID",
    "quotation_date"  : "Quotation Date",
    "customer"        : "Customer",
    "supplier"        : "Supplier",
    "material"        : "Material",
    "specification"   : "Specification",
    "equipment"       : "Equipment",
    "specifications"  : "Specifications",
    "quantity"        : "Quantity",
    "unit"            : "Unit",
    "unit_price"      : "Unit Price",
    "unit_price_inr"  : "Unit Price (INR)",
    "currency"        : "Currency",
    "delivery_time"   : "Delivery Time",
    "lead_time"       : "Lead Time",
    "moq"             : "MOQ",
    "available_stock" : "Available Stock",
    "terms"           : "Terms",
    "additional_notes": "Additional Notes",
}

# Fields stored in Document.metadata — excluded from page_content to avoid
# duplication. Provenance is preserved in metadata, not repeated in the text.
_METADATA_KEYS = {"source_file"}


def _record_to_text(record: dict) -> str:
    """
    Convert one quotation dict into a structured plain-text block for embedding.

    Only fields that are present and non-empty are included.
    Field name variations from the upstream schema are handled via _LABEL_MAP;
    any unrecognised key is auto-formatted as Title Case.

    Args:
        record: One quotation dict from the cleaned dataset.

    Returns:
        Multi-line string suitable for embedding, e.g.:
            Quotation ID: QTN-2026-001
            Customer: ABC Manufacturing Pvt. Ltd.
            Material: SS304 Stainless Steel Pipe
            ...
    """
    lines = []
    for key, value in record.items():
        if key in _METADATA_KEYS:
            continue
        if value is None or str(value).strip() == "":
            continue
        label = _LABEL_MAP.get(key, key.replace("_", " ").title())
        lines.append(f"{label}: {value}")

    return "\n".join(lines)


def load_json(json_path: str = JSON_PATH) -> List[Document]:
    """
    Read clean_data.json produced by 04_clean_validate.ipynb and convert
    every quotation record into a LangChain Document.

    Handles two JSON structures:
        dict  — clean_data.json top-level format:
                { "quotations": [...], "supplier_prices": [...], ... }
                Records are extracted from the key defined by JSON_KEY in config.
        list  — flat array (backward-compatible with earlier formats)

    Each Document produced contains:
        page_content : human-readable text block of all non-empty fields
        metadata     : { quotation_id, customer, supplier, currency,
                         source_file, file_name }

    Args:
        json_path: Path to the JSON file. Defaults to JSON_PATH in config.

    Returns:
        List of Document objects, one per valid record.
        Returns an empty list on any failure — the pipeline exits gracefully.
    """

    # 1. Validate the file exists
    if not os.path.exists(json_path):
        print(f"[loader] ⚠  JSON file not found: {json_path}")
        print(f"[loader]    Expected path : {json_path}")
        print( "[loader]    Copy clean_data.json from the pipeline output to this path,")
        print( "[loader]    or set the RAG_JSON_PATH environment variable.")
        return []

    # 2. Parse the JSON
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"[loader] ✖  JSON parse error in '{json_path}': {exc}")
        return []
    except OSError as exc:
        print(f"[loader] ✖  Cannot read '{json_path}': {exc}")
        return []

    # 3. Extract the records list
    #    clean_data.json is a nested dict — pull out the "quotations" key.
    #    A flat list is also accepted for backward compatibility.
    if isinstance(data, dict):
        records = data.get(JSON_KEY, [])
        if not isinstance(records, list):
            print(f"[loader] ✖  '{JSON_KEY}' key exists but is not a list "
                  f"(got {type(records).__name__}).")
            return []
        total_keys = list(data.keys())
        print(f"[loader] Detected nested JSON. Keys: {total_keys}")
        print(f"[loader] Using key '{JSON_KEY}' → {len(records)} record(s).")

    elif isinstance(data, list):
        records = data
        print(f"[loader] Detected flat JSON array → {len(records)} record(s).")

    else:
        print(f"[loader] ✖  Unexpected top-level JSON type: {type(data).__name__}. "
              "Expected dict or list.")
        return []

    # 4. Validate the records list is non-empty
    if not records:
        print(f"[loader] ⚠  '{JSON_KEY}' array is empty. "
              "Run 04_clean_validate.ipynb to regenerate clean_data.json.")
        return []

    print(f"[loader] Loading {len(records)} quotation record(s) from: {json_path}")

    # 5. Convert each record into a LangChain Document
    documents: List[Document] = []
    json_filename = os.path.basename(json_path)
    skipped = 0

    for idx, record in enumerate(records):

        # Skip non-dict entries without aborting the run
        if not isinstance(record, dict):
            print(f"[loader]   ⚠  Record #{idx}: not a dict "
                  f"(got {type(record).__name__}) — skipping.")
            skipped += 1
            continue

        if not record:
            print(f"[loader]   ⚠  Record #{idx}: empty dict — skipping.")
            skipped += 1
            continue

        try:
            page_content = _record_to_text(record)

            if not page_content.strip():
                print(f"[loader]   ⚠  Record #{idx}: produced no text — skipping.")
                skipped += 1
                continue

            metadata = {
                "quotation_id" : str(record.get("quotation_id", "")),
                "customer"     : str(record.get("customer", "")),
                "supplier"     : str(record.get("supplier", "")),
                "currency"     : str(record.get("currency", "")),
                # source_file comes from the record (set by preprocessing pipeline)
                # or falls back to the JSON filename
                "source_file"  : str(record.get("source_file", json_filename)),
                # file_name kept for backward compatibility
                "file_name"    : str(record.get("source_file", json_filename)),
            }

            documents.append(Document(page_content=page_content, metadata=metadata))

        except Exception as exc:
            # One bad record must never crash the entire ingestion run
            print(f"[loader]   ✖  Record #{idx}: failed to convert — {exc}")
            skipped += 1

    print(f"[loader] ✔  {len(documents)} document(s) ready  "
          f"({skipped} skipped).")
    return documents


# ── Dispatcher ─────────────────────────────────────────────────────────────────

def load_documents() -> List[Document]:
    """
    Public entry point for the loader — called by build_index.py.

    Routes to the correct loader based on DATA_SOURCE_TYPE in config.py:
        "json"  →  load_json()    primary pipeline (default)
        "pdf"   →  load_pdfs()    legacy fallback

    Returns:
        List[Document] ready for splitter.split_documents().
    """
    source = DATA_SOURCE_TYPE.strip().lower()

    if source == "json":
        print(f"[loader] DATA_SOURCE_TYPE='json' — loading from: {JSON_PATH}")
        return load_json()

    elif source == "pdf":
        print(f"[loader] DATA_SOURCE_TYPE='pdf' — loading from: {PDF_DIR}")
        return load_pdfs()

    else:
        print(f"[loader] ⚠  Unknown DATA_SOURCE_TYPE='{DATA_SOURCE_TYPE}'. "
              "Expected 'json' or 'pdf'. Defaulting to 'json'.")
        return load_json()


# ── Smoke-test ─────────────────────────────────────────────────────────────────
# Run directly to verify loading before building the index.
#   python loader.py
if __name__ == "__main__":
    docs = load_documents()
    if docs:
        first = docs[0]
        print("\n── Sample document (first record) ──")
        print(f"Source      : {first.metadata.get('source_file')}")
        print(f"Quotation ID: {first.metadata.get('quotation_id')}")
        print(f"Customer    : {first.metadata.get('customer')}")
        print(f"Supplier    : {first.metadata.get('supplier')}")
        print(f"\nText preview:\n{first.page_content[:500]}")
    else:
        print("\n[loader] No documents loaded. "
              "Verify clean_data.json exists at the path in config.py.")
