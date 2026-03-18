# NeonAI V5 — Technical Documentation

> **Local-First AI System** with Mode-Driven Intelligence, Voice Assistant, Tool Calling & Confidence Gating.

---

## 1. System Overview

NeonAI is an **offline-first AI system** where the LLM is one node in a larger decision pipeline — not the decision-maker. The system routes queries through tools, web search, and confidence gates before ever touching the LLM.

### Core Principles

| Principle | Implementation |
|:---|:---|
| **System > Model** | Waterfall engine decides the path, LLM only generates when needed |
| **Offline-First** | Runs 100% on localhost via Ollama — no cloud APIs required |
| **Mode Isolation** | Each mode (casual, coding, movie, exam, voice) has its own history, rules, and tools |
| **Tool-First** | Weather, calculator, notes, etc. respond in <1s without LLM |
| **Confidence Gating** | AI self-evaluates every answer (0-100%) and blocks hallucinations |

---

## 2. Technology Stack

### Backend

| Component | Technology | Purpose |
|:---|:---|:---|
| Server | **Flask** (Python 3.10+) | HTTP API, session management, routing |
| Auth | **SQLite** + **Werkzeug PBKDF2** | User accounts with hashed passwords |
| Sessions | **Flask Sessions** (HTTPOnly) | Secure per-user state isolation |
| CORS | **Flask-CORS** | Locked to localhost origins |

### AI / ML Models

| Model | Engine | Purpose | Size |
|:---|:---|:---|:---|
| **Llama 3.2 3B** | Ollama (local) | Text chat, voice assistant, reasoning | ~2 GB |
| **Qwen 2.5 Coder** | Ollama (local) | Coding mode (dedicated code model) | ~4 GB |
| **Whisper Base** | OpenAI Whisper (local) | Speech-to-Text (STT) | ~150 MB |
| **GPT-SoVITS** | Local API server | Text-to-Speech (TTS) voice cloning | ~1 GB |
| **all-MiniLM-L6-v2** | SentenceTransformers | Semantic intent routing (tools + commands) | ~80 MB |

### Data Storage

| Store | Technology | Purpose |
|:---|:---|:---|
| User Auth | SQLite (`user_data/auth/neon_users.db`) | Accounts, API keys |
| Movie Cache | SQLite (`user_data/cache/movie_cache.db`) | TMDB result caching |
| Exam Vectors | ChromaDB (local) | PDF embeddings for RAG |
| Notes | JSON files (`user_data/{id}/notes.json`) | Per-user notes |
| Memory | In-memory dict | Chat history per user+mode |

### External APIs (Optional)

| API | Purpose | Required? |
|:---|:---|:---|
| **Open-Meteo** | Weather data (free, no key) | No |
| **TMDB** | Movie details, trailers, recs | Optional (key in settings) |
| **Tavily** | Premium web search | Optional (key in settings) |
| **DuckDuckGo** | Free web search fallback | No |

---

## 3. Complete Request Flow

```mermaid
flowchart TD
    A["🧑 User Input"] --> B{Input Type?}
    
    B -->|"💬 Text"| C["server.py /chat"]
    B -->|"🎤 Voice Audio"| D["whisper_engine.py\n(Speech-to-Text)"]
    
    D --> E["command_router.py\n(Semantic Intent Match)"]
    E -->|"System Command\n(volume, apps, wifi)"| F["llm_command_executor.py\n(OS-level execution)"]
    E -->|"Not a Command"| C
    
    C --> G{Pure Math?}
    G -->|"Yes"| H["calculator.safe_eval\n(AST-based, no eval)"]
    H --> Z["📤 Return Response"]
    
    G -->|"No"| I["tool_router.py\n(Semantic Router)"]
    I -->|"🌤 Weather"| J["weather.py\n(Open-Meteo API)"]
    I -->|"🧮 Calculator"| K["calculator.py\n(AST Math)"]
    I -->|"📝 Notes"| L["notes.py\n(JSON CRUD)"]
    I -->|"💻 System"| M["system_info.py\n(psutil)"]
    I -->|"🎵 Music"| N["music.py\n(YouTube Music)"]
    I -->|"🌐 Browser"| O["browser_control.py"]
    I -->|"📖 Web Reader"| P["web_reader.py\n(BeautifulSoup)"]
    
    J & K & L & M & N & O & P --> Z
    
    I -->|"No Tool Match"| Q["waterfall.py\n(Decision Engine)"]
    
    Q --> R{Need Web Data?}
    R -->|"Yes"| S["search_adapter.py\n(Tavily / DuckDuckGo)"]
    S --> T["hybrid_llm.py\n(Web + LLM Fusion)"]
    
    R -->|"No"| U["local_llm.py\n(Llama 3.2 via Ollama)"]
    
    T --> V["confidence_gate.py\n(Self-Evaluate 0-100%)"]
    U --> V
    
    V -->|"Score ≥ Threshold"| Z
    V -->|"Score < Threshold"| W["🔄 Regenerate / Block"]
    W --> Z
    
    F --> X["🔊 TTS Response\n(GPT-SoVITS)"]
    Z -->|"Voice Mode"| X
    
    style A fill:#1a1a2e,stroke:#00ffc8,color:#fff
    style Z fill:#1a1a2e,stroke:#00ffc8,color:#fff
    style X fill:#1a1a2e,stroke:#a855f7,color:#fff
    style F fill:#1a1a2e,stroke:#f97316,color:#fff
```

---

## 4. Mode Architecture

```mermaid
flowchart LR
    subgraph "🤖 Casual Mode"
        CA[Text Input] --> CB[Tool Router]
        CB --> CC[Waterfall Engine]
        CC --> CD[Llama 3.2 3B]
        CD --> CE[Confidence Gate]
    end
    
    subgraph "💻 Coding Mode"
        CO1[Code Query] --> CO2[Qwen 2.5 Coder\nCoding Prompt]
        CO2 --> CO3[Code Formatting]
    end
    
    subgraph "🎬 Movie Mode"
        MO1[Movie Query] --> MO2[TMDB API]
        MO2 --> MO3[Movie Card UI]
        MO1 --> MO4[Llama 3.2 3B\nMovie Prompt]
    end
    
    subgraph "📚 Exam Mode"
        EX1[Question] --> EX2["retriever.py\n(ChromaDB)"]
        EX2 --> EX3[Llama 3.2 3B\nRAG Prompt]
        EX3 -.->|"No PDF match"| EX4[❌ Refuse Answer]
    end
    
    subgraph "🎤 Voice Mode"
        VO1[Audio Blob] --> VO2[Whisper STT]
        VO2 --> VO3[Command Router]
        VO3 -->|System| VO4[OS Executor]
        VO3 -->|Chat| VO5[Llama 3.2 3B]
        VO5 --> VO6[GPT-SoVITS TTS]
    end
```

---

## 5. Voice Assistant Pipeline

```mermaid
sequenceDiagram
    participant U as 🧑 User
    participant MIC as 🎙️ Browser MediaRecorder
    participant W as Whisper (STT)
    participant CR as Command Router
    participant EX as OS Executor
    participant LLM as Llama 3.2 3B
    participant TTS as GPT-SoVITS (TTS)
    participant SPK as 🔊 Speaker
    
    U->>MIC: Speak
    MIC->>W: Audio Blob (WebM/WAV)
    W->>CR: Transcribed Text
    
    alt System Command (e.g. "Volume up")
        CR->>EX: action=volume_up, target=10
        EX->>SPK: ✅ Execute (PowerShell)
        EX->>TTS: "Volume increased by 10%"
    else Tool Query (e.g. "Weather in Mumbai")
        CR->>LLM: Route to Tool → Weather
        LLM->>TTS: "It's 32°C and sunny in Mumbai"
    else General Chat
        CR->>LLM: Generate conversational response
        LLM->>TTS: Response text
    end
    
    TTS->>SPK: .wav audio file
```

---

## 6. Semantic Router (Tool & Command Detection)

NeonAI uses **SentenceTransformers** (`all-MiniLM-L6-v2`) for intent classification instead of keyword matching.

```mermaid
flowchart TD
    A["User Text"] --> B["Encode with\nall-MiniLM-L6-v2"]
    B --> C["Cosine Similarity\nvs Intent Embeddings"]
    C --> D{Score > Threshold?}
    
    D -->|"Tool Router\n(threshold: 0.28)"| E["Route to Tool\n(weather, calc, notes...)"]
    D -->|"Command Router\n(threshold: 0.35)"| F["Route to System Action\n(volume, bluetooth, shutdown...)"]
    D -->|"Below threshold"| G["Pass to Waterfall\n(LLM handles it)"]
```

**How it works:**
1. Each tool/command has a list of example sentences (intents)
2. All example sentences are pre-encoded into embeddings at startup
3. User text is encoded and compared via cosine similarity
4. Highest-scoring intent above threshold wins

---

## 7. Waterfall Decision Engine

```mermaid
flowchart TD
    A["waterfall.py"] --> B{Mode?}
    
    B -->|"exam"| C["retriever.py\nSearch ChromaDB"]
    C --> D{Found in PDF?}
    D -->|"Yes"| E["Llama 3.2 + PDF Context"]
    D -->|"No"| F["Refuse: Not in syllabus"]
    
    B -->|"casual / coding"| G{Internet Available?}
    G -->|"Yes"| H["search_adapter.py\nFetch Web Results"]
    H --> I["hybrid_llm.py\nWeb + LLM Fusion"]
    G -->|"No"| J["local_llm.py\nPure Offline LLM"]
    
    B -->|"movie"| K["movie_adapter.py\nTMDB Lookup"]
    K --> L["Llama 3.2 + Movie Context"]
    
    B -->|"voice_assistant"| M["assistant_llm.py\nLlama 3.2 Fast Inference"]
    
    E & I & J & L & M --> N["confidence_gate.py\nSelf-Evaluate (0-100%)"]
    N -->|"Pass"| O["✅ Return Response"]
    N -->|"Fail"| P["🔄 Regenerate with\nweb context"]
```

---

## 8. Data Flow & User Isolation

```mermaid
flowchart TD
    subgraph "User 1"
        U1[Session: user_1] --> H1["History:\nuser_1_casual\nuser_1_coding\nuser_1_movie"]
        U1 --> N1["Notes:\nuser_data/1/notes.json"]
        U1 --> M1["Media:\nuser_data/1/media/"]
        U1 --> K1["API Keys:\nSQLite (encrypted)"]
    end
    
    subgraph "User 2"
        U2[Session: user_2] --> H2["History:\nuser_2_casual\nuser_2_coding"]
        U2 --> N2["Notes:\nuser_data/2/notes.json"]
        U2 --> M2["Media:\nuser_data/2/media/"]
        U2 --> K2["API Keys:\nSQLite (encrypted)"]
    end
    
    H1 & H2 --> MEM["In-Memory HISTORY Dict\n(LRU capped at 50 users)"]
```

---

## 9. Module Dependency Map

```mermaid
graph TD
    SERVER["server.py"] --> BRAIN["brain/"]
    SERVER --> MODELS["models/"]
    SERVER --> TOOLS["tools/"]
    SERVER --> VOICE["voice/"]
    SERVER --> WEB["web/"]
    SERVER --> EXAM["exam/"]
    SERVER --> UTILS["utils/"]
    
    BRAIN --> |waterfall| MODELS
    BRAIN --> |waterfall| TOOLS
    BRAIN --> |waterfall| WEB
    BRAIN --> |waterfall| EXAM
    
    TOOLS --> |web_reader| MODELS
    TOOLS --> |weather| BRAIN
    
    VOICE --> |tts_engine| EXT_TTS["GPT-SoVITS\n(localhost:9880)"]
    VOICE --> |whisper_engine| EXT_WHISPER["Whisper Model\n(Local)"]
    
    MODELS --> EXT_OLLAMA["Ollama Daemon\n(localhost:11434)"]
    
    EXAM --> EXT_CHROMA["ChromaDB\n(Local Vector Store)"]
    
    WEB -.-> EXT_TAVILY["Tavily API\n(Optional)"]
    WEB -.-> EXT_DDG["DuckDuckGo\n(Free Fallback)"]
    WEB -.-> EXT_TMDB["TMDB API\n(Optional)"]
    
    style EXT_OLLAMA fill:#f97316,stroke:#fff,color:#fff
    style EXT_TTS fill:#a855f7,stroke:#fff,color:#fff
    style EXT_WHISPER fill:#0ea5e9,stroke:#fff,color:#fff
    style EXT_CHROMA fill:#22c55e,stroke:#fff,color:#fff
    style EXT_TAVILY fill:#666,stroke:#fff,color:#fff
    style EXT_DDG fill:#666,stroke:#fff,color:#fff
    style EXT_TMDB fill:#666,stroke:#fff,color:#fff
```

> **Solid lines** = always used. **Dashed lines** = optional/internet-dependent.

---

## 10. Security Architecture

| Layer | Protection |
|:---|:---|
| **Authentication** | PBKDF2 hashed passwords, min 8 chars |
| **Sessions** | HTTPOnly cookies, rotation on login, 30-day expiry |
| **Authorization** | All write/reset endpoints require valid `session['user_id']` |
| **Math Evaluation** | Safe AST parser (no `eval()`) |
| **CORS** | Locked to `localhost:5000` and `127.0.0.1:5000` |
| **Data Isolation** | Per-user directories, per-user notes, per-user pending commands |
| **Database** | All SQLite connections use `try/finally` (no leaks) |
| **Secrets** | `NEON_SECRET` loaded from `.env` (never hardcoded) |

---

## 11. API Endpoints

| Method | Endpoint | Auth | Purpose |
|:---|:---|:---|:---|
| GET | `/` | No | Serve main chat UI |
| GET | `/login` | No | Serve login page |
| POST | `/auth/signup` | No | Register new account |
| POST | `/auth/login` | No | Login + session rotation |
| GET | `/auth/logout` | Yes | Clear session |
| POST | `/chat` | Yes | Main chat endpoint (all modes) |
| POST | `/voice` | Yes | Voice transcribe + respond |
| POST | `/upload-bg` | Yes | Upload background media |
| POST | `/upload-voicebg` | Yes | Upload voice mode video |
| POST | `/upload-dp` | Yes | Upload profile picture |
| POST | `/upload-pdf` | Yes | Upload exam PDF |
| POST | `/reset-exam-db` | Yes | Clear exam vector store |
| POST | `/reset` | Yes | Clear chat history |
| POST | `/set-search-key` | Yes | Save Tavily API key |
| POST | `/set-tmdb-key` | Yes | Save TMDB API key |
| GET | `/health` | No | System status (Ollama, TTS, internet) |

---

*Generated: March 2026 • NeonAI V5*
