# Mention Pipeline

A Python-based pipeline for processing, deduplicating, batching, and enriching mentions using an LLM. The pipeline is designed to be modular, testable, and extensible, making it suitable for processing mentions from multiple tenants while tracking usage and reporting enrichment results.

---

## Features

- Parse and process mentions from JSON input
- Multi-tenant support
- Mention deduplication
- Token estimation for batching
- Configurable batching by token count
- LLM-powered enrichment
  - Sentiment analysis
  - Summary generation
  - Topic extraction
- Failure tracking
- Tenant-level usage and cost reporting
- Comprehensive testing support

---

## Project Structure

```text
pipeline/
│
├── data/                     # Input JSON files
│
├── mention_pipeline/         # Source code
│   ├── __init__.py
│   ├── models.py
│   ├── config.py
│   ├── batch.py
│   ├── deduplication.py
│   ├── exceptions.py
|   ├── llm.py
|   ├── retry.py
│   
│
├── tests/                   # Unit and integration tests
│   ├── __init__.py
|   ├── test_batch.py
|   ├── test_dedup.py
|   ├── test_llm.py
|   ├── test_retry.py
|
├── pyproject.toml           # Project configuration
├── Makefile                 # Common development commands
├── README.md
└── .gitignore
```

---

## Requirements

- Python 3.11+
- Git
- pip

---

## Small Decisions

- Handled the mentions that exceeded the max token limits by marking it as failed.
- Used the Jaccard Similarity for deduplication as this project is suppose to run for small data, so i used the jaccard similarity because of its simplicity.
