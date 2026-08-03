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
│   
│   
│   
│   
│   
│
├── tests/                   # Unit and integration tests
│
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
