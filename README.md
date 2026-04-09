# chefplusplus

Django app for CS 2340. Code is in **`app/`**; AWS CDK is in **`infrastructure/`**.

**Prerequisites:** Python **3.10** on your PATH (`python3` on macOS, `python` or `py -3` on Windows). Optional: Docker, Node 18+ (for CDK only).

## Install (one line)

**macOS / Linux**

```bash
cd app && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**Windows** (Command Prompt or PowerShell 7+)

```bat
cd app && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
```

*PowerShell 5:* run the same commands separated by `;` instead of `&&`, or use **cmd**. If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `cmd` and `.\.venv\Scripts\activate.bat`.

## Run

From the **`app/`** directory with the venv **activated** (you should see `(.venv)` in your prompt):

```bash
python manage.py migrate
python manage.py runserver
```

Open [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/). For admin login: `python manage.py createsuperuser`.

To listen on all interfaces (e.g. another device on your network): `python manage.py runserver 0.0.0.0:8000` and use your machine’s LAN URL.

## Vertex AI chat integration

This branch wires the home chat UI to `POST /api/chat`, backed by `app/home/vertex_chat.py`.

### Required environment variables

- `GOOGLE_CLOUD_PROJECT`
- `VERTEX_CHAT_MODEL`
- `VERTEX_AI_LOCATION` (optional, defaults to `us-central1`)
- `VERTEX_RAG_CORPUS` (optional; when present, enables Vertex RAG retrieval)
- `VERTEX_RAG_TOP_K` (optional; defaults to `8`)

### Notes for CI

- Tests in `home/tests.py` mock the AI call path, so CI does **not** need cloud credentials.
- Runtime uses `google-cloud-aiplatform` (added to `app/requirements.txt`).

## Docker

From the **repo root:** `docker build -t chefplusplus .` then `docker run --rm -p 8000:8000 chefplusplus` → [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/).

## AWS (CDK)

```bash
cd infrastructure && npm install && npx cdk deploy
```

Bootstrap once per account/region: `npx cdk bootstrap aws://ACCOUNT/REGION`. See `lib/config/stack-parameters.ts` for deploy parameters; build/push the image to ECR before deploying.

## Layout

| Path | Role |
|------|------|
| `app/` | Django (`manage.py`, `requirements.txt`) |
| `Dockerfile` | Image for Gunicorn + WhiteNoise |
| `infrastructure/` | CDK TypeScript (`lib/config/`, `lib/constructs/`) |
