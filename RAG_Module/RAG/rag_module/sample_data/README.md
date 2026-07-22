# sample_data/

This folder contains **legacy development PDFs** that were used to test the RAG module
before the preprocessing pipeline was integrated.

> ⚠️ These files are **NOT** consumed by the active pipeline.

## Why they were moved here

The RAG module previously read raw quotation PDFs directly from `data/`.
That approach has been replaced by the full preprocessing pipeline:

```
01_excel_ingestion.ipynb
        ↓
02_pdf_ingestion.ipynb
        ↓
03_market_api.py
        ↓
04_clean_validate.ipynb
        ↓
clean_data.json   ←  this is what the RAG module now consumes
```

## To use these files for testing

If you want to test the legacy PDF pipeline:

1. Set `DATA_SOURCE_TYPE = "pdf"` in `config.py`
2. Copy the PDFs into `data/`
3. Run `python build_index.py`
