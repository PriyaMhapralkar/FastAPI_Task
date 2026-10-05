# Document & Chat REST API

A small FastAPI backend that allows users to:

- Upload documents
- View uploaded document metadata
- Send chat messages

This project does not use AI, RAG, or a database.

## Features

- Upload PDF, TXT, MD, DOC, and DOCX files
- Validate uploaded file types
- Generate a unique UUID for every uploaded document
- Save uploaded files locally in the `uploads/` directory
- Store document metadata in memory
- List uploaded documents
- Simple chat endpoint
- Pydantic request and response validation
- Swagger UI documentation

## Tech Stack

- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- python-multipart

## Project Structure

```text
FastAPI_Task/
├── app/
│   ├── __init__.py
│   ├── main.py
│   └── schemas.py
├── uploads/
│   └── .gitkeep
├── .gitignore
├── README.md
└── requirements.txt