# AI Interview Coach

Owner/Author: N H Padma Priya

A modular Flask application that helps users practice interview questions, receive AI-powered feedback, and track progress.

## Features
- Adaptive question selection by weakest concept, no immediate repeats per category
- AI scoring using sentence-transformers (MiniLM), concept coverage, and structure heuristics
- Dashboard with user skill map and recommendations
- Voice input support on the interview page (browser-dependent)

## Project Structure
```
.
├── app/
│   ├── __init__.py            # App factory, config, logging
│   ├── routes.py              # All Flask routes (blueprint)
│   ├── ai/
│   │   └── analyzer_service.py# Model loading and answer analysis
│   └── utils/
│       └── text.py            # Concept extraction and helpers
├── templates/                 # Jinja2 templates
│   ├── index.html
│   ├── welcome.html
│   ├── dashboard.html
│   └── thankyou.html
├── static/                    # Static assets
│   └── images/
├── tests/                     # Unit tests
│   └── test_app.py
├── questions.json             # Question bank with ideal answers
├── wsgi.py                    # Entrypoint for running the app
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Dev/lint/test dependencies
├── Dockerfile                 # Container build
├── docker-compose.yml         # Local development with Docker
├── render.yaml                # Render deployment blueprint
├── .env.example               # Example environment configuration
├── .gitignore
├── .flake8
├── pytest.ini
└── README.md
```

## Setup (Local)
1. Python 3.11 recommended.
2. Create virtualenv and install deps:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Create .env from example if desired (optional):
   ```bash
   cp .env.example .env
   ```
4. Run the app:
   ```bash
   python wsgi.py
   # App: http://127.0.0.1:8000/
   ```

## Run Tests
```bash
pip install -r requirements-dev.txt
pytest
```

## Docker
```bash
docker build -t ai-interview-coach .
docker run -p 8000:8000 ai-interview-coach
```

Or with compose:
```bash
docker-compose up --build
```

## Deployment on Render
- This repo includes render.yaml. On Render, create a new Web Service from your GitHub repo.
- Environment variables:
  - SECRET_KEY (required; do not commit secrets)
  - MODEL_NAME (optional, default: all-MiniLM-L6-v2)
  - LOG_LEVEL (INFO/DEBUG)
  - PORT (Render sets PORT automatically; we also default to 8000)

## Configuration
- All runtime configuration uses environment variables.
- Never commit secrets. Use .env (local) and managed env vars (Render).

## Security Considerations
- SECRET_KEY is required for session cookies; set via environment variable in production.
- Cookies use HttpOnly and SameSite=Lax where set by the app.
- Avoid logging sensitive content.

## Notes
- The analyzer model is lazily loaded on first request to reduce startup time.
- Model artifacts are cached by sentence-transformers; container images can take time on first run.

## License
MIT
