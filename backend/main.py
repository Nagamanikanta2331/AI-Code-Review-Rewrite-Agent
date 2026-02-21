"""
AI Code Review & Rewrite Agent — Backend API
=============================================
Production-grade FastAPI server with Google Gemini API integration.
Model: Gemini 2.5 Flash | Inference: Google AI
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# ───────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
MODEL_ID: str = "gemini-2.5-flash"
TEMPERATURE: float = 0.3
MAX_TOKENS: int = 8192
TOP_P: float = 0.9

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

if not GEMINI_API_KEY:
    print("⚠️  GEMINI_API_KEY is missing — set it in backend/.env")

# ───────────────────────────────────────────────────────────────
# Gemini Client
# ───────────────────────────────────────────────────────────────
gemini_client: Optional[genai.Client] = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ───────────────────────────────────────────────────────────────
# FastAPI Application
# ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Code Review & Rewrite Agent",
    description="Reviews, rewrites and improves code with Google Gemini 2.5 Flash.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ───────────────────────────────────────────────────────────────
# Pydantic Models
# ───────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    model: str
    gemini_connected: bool


class ReviewRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field(default="python")
    instructions: Optional[str] = Field(default=None)


class ReviewResponse(BaseModel):
    result: str
    model: str
    tokens_used: Optional[int] = None


class RewriteRequest(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field(default="python")


class RewriteResponse(BaseModel):
    rewritten_code: str
    improvements: list[str]
    model: str
    tokens_used: Optional[int] = None


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    code: str = Field(default="")
    language: str = Field(default="python")
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    model: str
    tokens_used: Optional[int] = None


class ConvertRequest(BaseModel):
    code: str = Field(..., min_length=1)
    from_language: str = Field(default="python")
    to_language: str = Field(default="javascript")


class ConvertResponse(BaseModel):
    converted_code: str
    notes: list[str]
    model: str
    tokens_used: Optional[int] = None


# ───────────────────────────────────────────────────────────────
# Prompt Engineering
# ───────────────────────────────────────────────────────────────
REVIEW_SYSTEM_PROMPT = """
You are a senior software engineer performing a clear, production-grade code review.

GOAL:
Provide a structured, concise, and easy-to-understand review.
Avoid long paragraphs. No unnecessary explanations. Focus only on real issues.

REVIEW CHECKLIST:
- Bugs & Logic Errors
- Security Risks
- Performance Issues
- Error Handling Problems
- Readability & Best Practices

SEVERITY LEVELS:
🔴 Critical  → Crashes, security risks, data loss
🟠 High      → Logic errors, unhandled exceptions, major flaws
🟡 Medium    → Code smells, missing validation, improvement areas
🔵 Low       → Style or minor readability improvements

RULES:
1. Keep each issue explanation under 3 lines.
2. Be specific — mention exact variable names and line numbers.
3. Do NOT repeat obvious things.
4. Do NOT over-explain.
5. Only include real, meaningful issues.

OUTPUT FORMAT:

══════════════════════════════
📊 REVIEW SUMMARY
══════════════════════════════
🔴 Critical : X
🟠 High     : X
🟡 Medium   : X
🔵 Low      : X
Total Issues: X

Progress:
Critical  : 🔴🔴 (X)
High      : 🟠🟠🟠 (X)
Medium    : 🟡 (X)
Low       : 🔵 (X)

══════════════════════════════
🔍 DETAILED FINDINGS
══════════════════════════════

### 🔴 [Short Issue Title]
Line(s): X
Problem: Short explanation.
Fix:
```python
corrected code snippet"""


REWRITE_SYSTEM_PROMPT = """
You are a senior software engineer rewriting code clearly and minimally.

GOAL:
Fix and improve the code while keeping it simple and proportional to the original size.

CORE RULE:
If the input code is small, keep the output small.
Do NOT over-engineer.

YOU MUST:
- Fix bugs and logical errors.
- Improve clarity and readability.
- Preserve the original intent.
- Keep structure similar unless necessary to change.
- Add minimal comments only if truly helpful.

YOU MUST NOT:
- Add unnecessary functions, classes, or abstractions.
- Add example usage unless explicitly requested.
- Add excessive comments or documentation.
- Introduce new features not present in the original code.
- Make the code significantly longer without strong reason.

OUTPUT FORMAT:
You MUST return a valid JSON object with exactly two keys:
- "rewritten_code": a string containing the clean corrected code
- "improvements": an array of strings, each a short bullet explaining an important fix (max 5)

Example:
{"rewritten_code": "print('Hello, World!')", "improvements": ["No changes needed."]}

Do NOT include markdown, code fences, or any text outside the JSON object.
"""

CHAT_SYSTEM_PROMPT = """
You are a helpful AI coding assistant embedded in a code review tool.
The user may provide a code snippet for context. Answer questions about the code clearly and concisely.

RULES:
1. If code context is provided, refer to it when answering.
2. Provide short, accurate, and actionable answers.
3. Use code snippets in your answers when helpful (wrap them in markdown fenced code blocks).
4. If the question is unrelated to programming, politely redirect the user.
5. Be friendly but professional.
6. Format your response with Markdown for readability.
"""

CONVERT_SYSTEM_PROMPT = """
You are a world-class software engineer who converts code between programming languages with perfect accuracy.

GOAL:
Accurately convert the given source code into the EXACT target language specified by the user.
Pay very close attention to the target language — do NOT default to JavaScript or any other language.

RULES:
1. The output code MUST be valid, compilable/runnable code in the TARGET language only.
2. Preserve the original logic, control flow, and intent exactly.
3. Use idiomatic patterns, syntax, and conventions of the TARGET language.
4. Convert language-specific constructs (print, types, string formatting, etc.) to their proper TARGET language equivalents.
5. For statically typed languages (C, C++, Java, Go, Rust, etc.), add proper type declarations, includes/imports, and a main function/entry point if the original code has top-level statements.
6. If the source uses a library, use the equivalent library in the target language or note that no direct equivalent exists.
7. Keep the converted code clean, readable, and properly indented.
8. Do NOT add extra features or code not in the original.
9. Do NOT output code in any language other than the specified target language.

LANGUAGE-SPECIFIC GUIDANCE:
- C: Use #include <stdio.h>, printf(), proper main() function, explicit types.
- C++: Use #include <iostream>, cout, proper main(), std:: namespace.
- Java: Use public class with main method, System.out.println.
- Go: Use package main, fmt.Println, func main().
- Rust: Use fn main(), println!() macro, proper ownership.
- Python: Use print(), def for functions, no type annotations unless in original.
- JavaScript: Use console.log(), function or arrow functions.
- TypeScript: Add type annotations, use console.log().

OUTPUT FORMAT:
You MUST return a valid JSON object with exactly two keys:
- "converted_code": a string containing ONLY the converted code in the target language
- "notes": an array of strings, each a short note about conversion decisions (max 5)

Example (Python to C):
{"converted_code": "#include <stdio.h>\n\nint main() {\n    printf(\"Hello, World!\\n\");\n    return 0;\n}", "notes": ["Converted print() to printf()", "Added main() entry point required by C"]}

Do NOT include markdown, code fences, or any text outside the JSON object.
"""

# ───────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────
def _ensure_gemini() -> None:
    """Raise 503 if Gemini client is not initialised."""
    if gemini_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API key is not configured. Set GEMINI_API_KEY in backend/.env",
        )


def _call_llm(system: str, user: str, json_mode: bool = False) -> tuple[str, Optional[int]]:
    """Call Google Gemini with retry logic and return (content, total_tokens)."""
    _ensure_gemini()

    max_retries = 5
    for attempt in range(max_retries):
        try:
            config = types.GenerateContentConfig(
                system_instruction=system,
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS,
                top_p=TOP_P,
            )
            if json_mode:
                config = types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_TOKENS,
                    top_p=TOP_P,
                    response_mime_type="application/json",
                )

            response = gemini_client.models.generate_content(
                model=MODEL_ID,
                contents=user,
                config=config,
            )
            content = response.text
            tokens = None
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                tokens = response.usage_metadata.total_token_count
            return content, tokens
        except Exception as exc:
            error_msg = str(exc).lower()
            if "rate" in error_msg or "quota" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 10  # 10s, 20s, 30s, 40s
                    print(f"[Gemini] Rate limited (attempt {attempt+1}/{max_retries}). Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Gemini rate limit exceeded. Free tier allows only 10 requests/minute. Please wait ~60 seconds and try again.",
                )
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"Gemini API error: {str(exc)}")

    raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Gemini API failed after retries.")


def extract_json(raw: str) -> dict:
    """Robust JSON extraction from LLM output with multi-strategy parsing."""
    if not raw or not isinstance(raw, str):
        raise ValueError("Empty or invalid response from model")

    # Strategy 1 — direct parse
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2 — strip markdown code fences
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 3 — extract first JSON object
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Strategy 4 — manually extract rewritten_code and improvements
    code_match = re.search(r'"rewritten_code"\s*:\s*"([\s\S]*?)"(?:\s*,\s*"improvements")', raw)
    imp_match = re.search(r'"improvements"\s*:\s*\[([\s\S]*?)\]', raw)
    if code_match:
        code_val = code_match.group(1)
        improvements = []
        if imp_match:
            improvements = re.findall(r'"([^"]*)"', imp_match.group(1))
        return {"rewritten_code": code_val, "improvements": improvements}

    raise ValueError("Failed to parse JSON from model response")


def _serve_html(filename: str) -> FileResponse:
    """Return an HTML file from the frontend directory or raise 404."""
    path = FRONTEND_DIR / filename
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{filename} not found at {path}")
    return FileResponse(path, media_type="text/html")


# ───────────────────────────────────────────────────────────────
# Routes — Health
# ───────────────────────────────────────────────────────────────
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return empty favicon to suppress 404."""
    from fastapi.responses import Response
    # 1x1 transparent PNG favicon
    import base64
    ico = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return Response(content=ico, media_type="image/png")


@app.get("/", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health-check endpoint."""
    return HealthResponse(
        status="API Connected",
        model=MODEL_ID,
        gemini_connected=gemini_client is not None,
    )


# ───────────────────────────────────────────────────────────────
# Routes — Code Review
# ───────────────────────────────────────────────────────────────
@app.post("/review", response_model=ReviewResponse, tags=["Code Review"])
async def review_code(req: ReviewRequest):
    """Review code with structured severity categories and line-by-line feedback."""
    focus = f"\n\nAdditional focus areas: {req.instructions}" if req.instructions else ""
    user_prompt = f"Language: {req.language}\n\n```{req.language}\n{req.code}\n```{focus}"

    content, tokens = _call_llm(REVIEW_SYSTEM_PROMPT, user_prompt)

    return ReviewResponse(result=content, model=MODEL_ID, tokens_used=tokens)


# ───────────────────────────────────────────────────────────────
# Routes — Code Rewrite (structured JSON)
# ───────────────────────────────────────────────────────────────
@app.post("/api/rewrite", response_model=RewriteResponse, tags=["Code Rewrite"])
async def rewrite_code(req: RewriteRequest):
    """Rewrite code to production quality — returns structured JSON."""
    user_prompt = f"Language: {req.language}\n\n```{req.language}\n{req.code}\n```"

    content, tokens = _call_llm(REWRITE_SYSTEM_PROMPT, user_prompt, json_mode=True)

    try:
        parsed = extract_json(content)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"Model returned invalid response. Please retry. ({exc})")

    rewritten = parsed.get("rewritten_code", "")
    improvements = parsed.get("improvements", [])

    if not rewritten:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Model did not return rewritten code.")

    return RewriteResponse(
        rewritten_code=rewritten,
        improvements=improvements if isinstance(improvements, list) else [str(improvements)],
        model=MODEL_ID,
        tokens_used=tokens,
    )


# ───────────────────────────────────────────────────────────────
# Routes — Chat
# ───────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(req: ChatRequest):
    """Chat with the AI about code — supports conversation history."""
    # Build user prompt with optional code context
    parts = []
    if req.code.strip():
        parts.append(f"Code context ({req.language}):\n```{req.language}\n{req.code}\n```\n")

    # Append conversation history
    for msg in req.history[-10:]:  # Keep last 10 messages for context
        parts.append(f"{msg.role}: {msg.content}")

    parts.append(f"user: {req.message}")
    user_prompt = "\n\n".join(parts)

    content, tokens = _call_llm(CHAT_SYSTEM_PROMPT, user_prompt)

    return ChatResponse(reply=content or "Sorry, I couldn't generate a response.", model=MODEL_ID, tokens_used=tokens)


# ───────────────────────────────────────────────────────────────
# Routes — Code Conversion
# ───────────────────────────────────────────────────────────────
@app.post("/api/convert", response_model=ConvertResponse, tags=["Code Conversion"])
async def convert_code(req: ConvertRequest):
    """Convert code from one programming language to another."""
    user_prompt = f"Convert the following {req.from_language} code to {req.to_language}.\n\nSOURCE LANGUAGE: {req.from_language}\nTARGET LANGUAGE: {req.to_language}\n\nThe output MUST be valid {req.to_language} code. Do NOT output any other language.\n\n```{req.from_language}\n{req.code}\n```"

    content, tokens = _call_llm(CONVERT_SYSTEM_PROMPT, user_prompt, json_mode=True)

    try:
        parsed = extract_json(content)
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"Model returned invalid response. Please retry. ({exc})")

    converted = parsed.get("converted_code", "")
    notes = parsed.get("notes", [])

    if not converted:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Model did not return converted code.")

    return ConvertResponse(
        converted_code=converted,
        notes=notes if isinstance(notes, list) else [str(notes)],
        model=MODEL_ID,
        tokens_used=tokens,
    )


# ───────────────────────────────────────────────────────────────
# Routes — Frontend Pages
# ───────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse, tags=["Frontend"])
async def serve_login():
    """Serve login page."""
    return _serve_html("login.html")


@app.get("/app", response_class=HTMLResponse, tags=["Frontend"])
async def serve_app():
    """Serve main application page."""
    return _serve_html("index.html")


# Mount static assets from frontend folder
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ───────────────────────────────────────────────────────────────
# Entry Point — python main.py
# ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    print("=" * 56)
    print("  AI Code Review & Rewrite Agent")
    print(f"  Model   : {MODEL_ID} (Google Gemini)")
    print(f"  Server  : http://localhost:8000")
    print(f"  Login   : http://localhost:8000/login")
    print(f"  App     : http://localhost:8000/app")
    print(f"  API Docs: http://localhost:8000/docs")
    print("=" * 56)

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
