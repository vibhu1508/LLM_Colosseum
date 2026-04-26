<div align="center">

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=35&pause=1000&color=0EA5E9&center=true&vCenter=true&width=800&height=80&lines=Prompt+Engineering+Healthcare+Lab;Local+LLM+Testing+Playground;Compare+Multiple+Models+Instantly)](https://git.io/typing-svg)

**A local classroom portal for Prompt Engineering activity execution in the Healthcare Information Assistant domain (non-diagnostic).**

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Angular](https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=Ollama&logoColor=white)

<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />
</div>

## ✨ What this app supports

- 🔄 **Dynamic multi-model comparison:** Compare prompts across 1 to N columns simultaneously.
- 🦙 **Ollama local model fan-out:** Send a single prompt to multiple locally hosted models.
- 📝 **Advanced Prompt Configuration:** Dedicated fields for required assignment elements:
  - `Role`, `Constraints`, `Tone`, `Safety instructions`, `Output format`
- 🎯 **Flexible Output Modes:** Switch between Natural language text and Structured JSON.
- 📊 **Global Shared Run Log:** Real-time visibility into all user runs.
- ⚖️ **Manual Scoring System:** Evaluate outputs on:
  - *Accuracy*, *Clarity*, *Relevance*, and specific *Failure tags*.

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 📂 Project Structure

```text
├── 🐍 backend/         # FastAPI APIs, Ollama integration, SQLite logging
└── 🅰️ frontend/        # Angular 18+ dashboard UI
```

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## ⚙️ Setup & Installation

### 1. Configure Ollama

Ensure [Ollama](https://ollama.com/) is running locally and your desired models are pulled.

```bash
# Example
ollama pull llama3
ollama serve
```

Update `backend/model_catalog.json` and replace the entries with your local models (keep `id`, `name`, `symbol`, `provider` keys intact).

### 2. Run the Backend

```powershell
cd backend

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Setup Environment variables
copy .env.example .env

# Run the API
uvicorn app.main:app --reload --port 8000
```
*(Optional: edit `.env` with `OLLAMA_BASE_URL` if it's not the default `http://127.0.0.1:11434`)*

### 3. Run the Frontend

```powershell
cd frontend

# Install packages
npm install

# Start development server
npm start
```

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## 🌐 URLs & API Overview

| Service | Local URL |
|---------|-----------|
| **Frontend UI** | `http://localhost:4200` |
| **Backend API** | `http://127.0.0.1:8000` |
| **Ollama Server** | `http://127.0.0.1:11434` |

### 🔌 Core API Endpoints

- `GET /api/models` - List available models
- `POST /api/compare` - Run one prompt against selected models
- `GET /api/runs` - Read global shared logs
- `POST /api/evaluate` - Save manual evaluation for output

<br/>
<img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" width="100%" />

## ⚠️ Notes

> [!IMPORTANT]  
> This system is **educational and non-diagnostic** by design. It should not be used for real healthcare diagnostics.

> [!NOTE]  
> - Backend stores logs in local SQLite database file: `backend/prompt_lab.db`.
> - JSON mode validates model output and stores the raw response even when invalid.
