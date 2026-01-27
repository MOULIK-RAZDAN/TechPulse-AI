# TechPulse AI: Real-time Tech Intelligence RAG

**TechPulse AI** is a high-performance **Retrieval-Augmented Generation (RAG)** system designed to aggregate, analyze, and synthesize **technology industry developments in real time**. It combines a distributed streaming architecture with **local-first LLM inference** to deliver **accurate, source-backed insights** from fast-moving tech news and research.

---

## System Architecture

TechPulse follows a **modular, event-driven microservices architecture** built for scalability, resilience, and low latency.

```text
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  RSS / API      │      │  Data Pipeline   │      │ Preprocessing   │
│  Web Scrapers  │─────▶│  - Fetch (30m)   │─────▶│  - Chunk (800)  │
└─────────────────┘      │  - Clean HTML    │      │  - Metadata     │
                         └──────────────────┘      └────────┬────────┘
                                                            │
                                                            ▼
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│   Frontend UI   │      │   RAG Pipeline   │      │  Vector Store   │
│ - Chat & Trends │◀─────│ Query → Retrieve │◀─────│ (Qdrant + PG)   │
│ - Source Links  │      │ → Generate       │      │ + Stable IDs   │
└─────────────────┘      └──────────────────┘      └─────────────────┘
```

### Data Flow Overview

* **Data Ingestion**: RSS feeds and web scrapers collect new content every **30 minutes**.
* **Streaming (Kafka)**: Raw articles are published to the `raw_articles` topic.
* **Embedding Service**:

  * Recursive chunking (~800 tokens)
  * Embeddings generated via **Ollama (`nomic-embed-text`, 768 dims)**
* **Indexer Service**:

  * Dual indexing into **PostgreSQL (metadata)** and **Qdrant (vector search)**
  * Deterministic hashing for strict deduplication
* **RAG Backend**:

  * Hybrid retrieval (Vector DB + live web search)
  * Answer generation using **Claude 3.5 Sonnet** or **local Llama 3.2** fallback

---

## Tech Stack

### Frontend

* **Next.js**
* **Tailwind CSS**
* **Lucide React**

### Backend

* **FastAPI**
* **Python 3.10+**

### AI / ML

* **Ollama** (local embeddings & LLM)
* **Anthropic Claude API**
* **LangChain** (chunking & orchestration)

### Data & Infra

* **Vector DB**: Qdrant
* **Relational DB**: PostgreSQL
* **Message Broker**: Apache Kafka
* **Cache**: Redis

### DevOps

* **Podman / Docker Compose**

---

## Key Features

* **Hybrid Search**
  Automatically falls back to **Google News** and **DuckDuckGo** when local data is insufficient or when queries require real-time context.

* **Deterministic Deduplication**
  URL-based **MD5 hashing** ensures duplicate articles or chunks never pollute the vector store.

* **Source-Cited Answers**
  Every response includes **numbered, clickable citations** linking to original blogs, documentation, or research papers (e.g., arXiv).

* **Local-First Resilience**
  If Anthropic APIs are unavailable, the system **automatically falls back to a local Llama 3.2 model** via Ollama.

---

## Getting Started

### Prerequisites

* **Podman** or **Docker**
* **Ollama** running locally with:

  * `nomic-embed-text`
  * `llama3.2`

---

### Installation

#### Clone the Repository

```bash
git clone https://github.com/your-username/TechPulse.git
cd TechPulse
```

#### 2️⃣ Configure Environment Variables

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=your_key_here
OLLAMA_HOST=http://host.containers.internal:11434
POSTGRES_PASSWORD=changeme
REDIS_PASSWORD=changeme
```

#### 3️⃣ Start the Stack

```bash
podman-compose up -d
```

#### 4️⃣ Verify Services

```text
http://localhost:8000/health
```

---

## 📈 Roadmap & Future Enhancements

* [ ] **Asynchronous Parallel Search** (news + arXiv via asyncio)
* [ ] **Query Expansion & Correction** ("anthropi" → "Anthropic")
* [ ] **Streaming Responses** using Server-Sent Events (SSE)
* [ ] **Semantic Deduplication** via MinHash / SimHash

---

## 📄 License

Distributed under the **MIT License**. See the `LICENSE` file for details.

---

## 🧾 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you’d like to change.

---

### 📌 Tip

After saving this file:

```bash
git add README.md
git commit -m "docs: add formatted README and architecture overview"
git push
```
