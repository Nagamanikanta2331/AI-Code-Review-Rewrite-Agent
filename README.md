# AI Code Review & Rewrite Agent

AI Code Review & Rewrite Agent uses **Google Gemini 2.5 Flash** to deliver real-time bug detection, security checks, and optimized code rewriting via **FastAPI** and a modern web UI — improving code quality and developer speed.

---

## Features

- **Code Review** — Structured, severity-graded feedback (Critical / High / Medium / Low) with line-by-line analysis
- **Code Rewrite** — Automatically rewrites code to production quality with a list of improvements
- **Multi-Language Support** — Works with Python, JavaScript, TypeScript, Java, C++, and more
- **Modern Web UI** — Glass-morphism design with dark/light theme toggle and Monaco code editor
- **Login Page** — Clean authentication interface
- **Interactive API Docs** — Auto-generated Swagger UI at `/docs`
- **Retry Logic** — Built-in rate-limit handling and retry for Gemini API calls

---

## Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Backend    | Python, FastAPI, Uvicorn            |
| AI Model   | Google Gemini 2.5 Flash (`google-genai`) |
| Frontend   | HTML, CSS, JavaScript, Monaco Editor |
| Libraries  | Highlight.js, Marked.js, Font Awesome |

---

## Project Structure

```
AI-Code-Review-Rewrite-Agent/
├── backend/
│   ├── main.py            # FastAPI server & Gemini integration
│   ├── requirements.txt   # Python dependencies
│   ├── .env               # API key (not committed)
│   └── __init__.py
├── frontend/
│   ├── index.html         # Main app UI (code editor + results)
│   └── login.html         # Login page
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- A **Google Gemini API key** — get one at [Google AI Studio](https://aistudio.google.com/app/apikey)

### 1. Clone the Repository

```bash
git clone https://github.com/Nagamanikanta2331/AI-Code-Review-Rewrite-Agent.git
cd AI-Code-Review-Rewrite-Agent
```

### 2. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables

Create a `backend/.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Run the Server

```bash
cd backend
python main.py
```

The server starts at **http://localhost:8000**.

---

## Usage

| URL                          | Description              |
|------------------------------|--------------------------|
| http://localhost:8000/login   | Login page               |
| http://localhost:8000/app     | Main application UI      |
| http://localhost:8000/docs    | Swagger API documentation|

### API Endpoints

| Method | Endpoint       | Description                        |
|--------|----------------|------------------------------------|
| GET    | `/`            | Health check & API status          |
| POST   | `/review`      | Review code (returns markdown)     |
| POST   | `/api/rewrite` | Rewrite code (returns JSON)        |
| GET    | `/login`       | Serve login page                   |
| GET    | `/app`         | Serve main application page        |

### Example — Code Review Request

```bash
curl -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def add(a, b):\n    return a - b",
    "language": "python"
  }'
```

### Example — Code Rewrite Request

```bash
curl -X POST http://localhost:8000/api/rewrite \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def add(a, b):\n    return a - b",
    "language": "python"
  }'
```

---

## Screenshots

### Dark Theme
> Modern glass-morphism UI with Monaco code editor, severity-based review output, and one-click code rewriting.

### Light Theme
> Full light-mode support with smooth theme transitions.

---

## License

This project is open-source and available under the [MIT License](LICENSE).
