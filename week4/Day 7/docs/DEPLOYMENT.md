@'
# Deployment Runbook

## Local (no Docker) — for development

```bash
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000 --reload