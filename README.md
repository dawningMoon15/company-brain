# Company Brain

**Company Brain** is a multi-tenant SaaS knowledge management platform designed to centralize and interrogate enterprise documents. It allows organizations to securely upload internal documents, parse them at scale, and eventually query their proprietary knowledge base using Retrieval-Augmented Generation (RAG).

The platform solves the problem of fragmented enterprise knowledge by providing a unified, secure ingestion pipeline that transforms raw unstructured files (like PDFs) into structured, queryable data contexts for Large Language Models (LLMs).

---

## Current Architecture

The platform follows a decoupled, service-oriented architecture tailored for scalable AI ingestion and retrieval. 

### System Overview

```text
[ Client Application (Next.js) ]
              │
              ▼ (REST APIs / JWT)
[ FastAPI Backend Service ] ───▶ [ Supabase Storage (Object Store) ]
              │
              ▼ (SQLAlchemy)
[ Supabase PostgreSQL (Relational DB) ]
```

### Document Ingestion Pipeline

```text
Upload PDF ──▶ Save to Storage ──▶ Create Metadata ──▶ Extract Text (PyMuPDF)
                                                            │
                                                            ▼
                                                    [ Parsed Text DB ]
                                                            │
                                                     (Future Phases)
                                                            ▼
                                           Chunking ──▶ Embeddings ──▶ Vector DB
```

---

## Features

### ✅ Completed (Ingestion Layer)
* **JWT-based Authentication**: Secure user registration, login, and session management with password hashing.
* **Workspace Isolation**: Multi-tenant architecture where data is strictly partitioned by workspace.
* **Secure PDF Uploads**: Direct integration with Supabase Storage for reliable file hosting, including MIME type and size validation.
* **Document Metadata Management**: Full tracking of the document lifecycle (uploaded → parsed → failed).
* **Automated Parsing Pipeline**: Robust text extraction from raw PDFs using PyMuPDF, with graceful handling of corrupt pages and persistence of extracted text for downstream chunking.

### 🚀 Upcoming (Retrieval & Generation Layer)
* **Text Chunking**: Splitting extracted text into semantically cohesive blocks.
* **Embeddings Generation**: Converting text chunks into dense vector representations.
* **Semantic Retrieval**: Integrating a Vector Database to retrieve highly relevant context based on user queries.
* **AI Chat Interface**: Conversational UI powered by LLMs, grounded in the retrieved workspace context.

---

## Tech Stack

* **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3)
* **Database & ORM**: [PostgreSQL](https://www.postgresql.org/) (via [Supabase](https://supabase.com/)), [SQLAlchemy](https://www.sqlalchemy.org/)
* **Object Storage**: [Supabase Storage](https://supabase.com/docs/guides/storage)
* **Authentication**: Custom JWT (JSON Web Tokens) with `python-jose` and `passlib` (bcrypt)
* **PDF Processing**: [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/)
* **Frontend**: [Next.js](https://nextjs.org/) (Planned)

---

## Database Design

The relational schema is designed for strict multi-tenancy and auditability:

1. **Users**: Central identity table.
2. **Workspaces**: Represents an organization or project space. Owned by a User.
3. **Documents**: Belongs to a Workspace. Stores metadata (filename, size, storage path), extraction state, and the raw parsed text.

*Hierarchy: User ──(1:N)──▶ Workspace ──(1:N)──▶ Document*

---

## Security Design

Security is implemented at the API boundary and data layer:
* **Stateless Auth**: API routes are protected via standard JWT Bearer authentication.
* **Data Isolation**: Every document endpoint verifies that the authenticated user explicitly owns the parent workspace before allowing read/write operations.
* **Private Storage**: Supabase Storage buckets are private; access is strictly brokered by the backend API using Service Role keys, entirely bypassing client-side exposure.
* **Credential Protection**: Passwords are one-way hashed using bcrypt before persistence.

---

## Local Development Setup

### Prerequisites
* Python 3.10+
* A Supabase project (PostgreSQL + Storage)

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/dawningMoon15/company-brain.git
cd company-brain/backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Database
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres

# Auth Security
SECRET_KEY=your_secure_random_string_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Supabase Storage (Service Role Key required to bypass RLS)
SUPABASE_URL=https://[PROJECT_ID].supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_jwt
```

### 3. Startup

Start the local FastAPI development server:

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. API Documentation

Navigate to **http://127.0.0.1:8000/docs** to view the interactive Swagger UI and test the endpoints.

---

## API Overview

**Authentication**
* `POST /signup` - Register a new user
* `POST /login` - Authenticate and receive a JWT
* `GET /me` - Retrieve current authenticated user profile

**Workspaces**
* `POST /workspaces` - Create a new workspace
* `GET /workspaces` - List all owned workspaces
* `GET /workspaces/{id}` - Retrieve workspace details

**Documents (Ingestion & Parsing)**
* `POST /workspaces/{id}/upload` - Upload a PDF to a workspace and Supabase Storage
* `POST /documents/{id}/parse` - Trigger text extraction pipeline
* `GET /workspaces/{id}/documents` - List workspace documents
* `GET /documents/{id}` - Retrieve document metadata
* `DELETE /documents/{id}` - Delete document and associated data

---

## Future Roadmap

The immediate engineering focus is transitioning from the *Ingestion Phase* to the *Retrieval Phase*:
1. **Intelligent Chunking**: Implement semantic boundary detection to split parsed text logically.
2. **Embeddings Pipeline**: Integrate embedding models (e.g., OpenAI `text-embedding-3-small` or local variants).
3. **Vector Database Integration**: Expand PostgreSQL with `pgvector` for high-performance similarity search.
4. **Semantic Retrieval System**: Develop search endpoints that rank chunks by relevance to query vectors.
5. **Conversational AI**: Implement the final generation step, maintaining conversational memory (chat history) and citing specific document chunks as context.
