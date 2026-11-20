# Contributing Guidelines

Thank you for considering a contribution! Follow the steps below to keep the workflow smooth and reproducible.

## Getting Started
- Install backend dependencies inside a virtual environment:  
  `python -m venv .venv && . .venv/Scripts/activate && pip install -r backend/requirements.txt`
- Install frontend dependencies:  
  `cd frontend && npm install`
- Run the Flask API with `python backend/server.py` and launch the React app with `npm start` inside `frontend/`.

## Workflow
1. Fork the repository and create a feature branch (`git checkout -b feature/your-change`).
2. Keep commits focused. Group related updates together.
3. Run linting or formatting tools relevant to your changes (e.g., `black`, `flake8`, `npm run lint` if available).
4. Manually test the upload → processing → download pipeline before opening a pull request.

## Coding Standards
- Prefer English comments and documentation.
- Document non-obvious logic with concise comments.
- Follow existing formatting conventions in Python and JavaScript code.

## Submitting a Pull Request
When opening a PR, include:
- A short summary of the change and the motivation.
- Notes on testing performed.
- Any follow-up work that might be required.

We appreciate every contribution—thank you for helping improve Olive Detection Project!
