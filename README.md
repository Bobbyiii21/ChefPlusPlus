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

## Vertex AI Tools (`app/tools/`)

The `app/tools/` package provides a standalone Python toolkit for interacting with Google Cloud Vertex AI. It is **not** a Django app — just plain Python modules that front-end developers can import and call.

### Environment variables

All env-var access is centralised in `app/tools/env_config.py`. Variables are resolved in this order:

1. `os.environ` (shell exports, Docker, Cloud Run, etc.)
2. `.env` files loaded via `python-dotenv` (repo root, then `app/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | **yes** | — | GCP project ID |
| `VERTEX_AI_LOCATION` | no | `us-central1` | Vertex AI region |
| `VERTEX_CHAT_MODEL` | **yes** | — | Gemini model name (e.g. `gemini-2.0-flash`) |
| `VERTEX_RAG_CORPUS` | **yes** (for RAG) | — | Full corpus resource name |
| `VERTEX_RAG_TOP_K` | no | `8` | Number of RAG retrieval results |
| `GCS_BUCKET` | **yes** (for uploads) | — | Google Cloud Storage bucket name |

Import helpers instead of using `os.environ` directly:

```python
from tools.env_config import get_env, require_env

project = require_env("GOOGLE_CLOUD_PROJECT")   # raises on missing
region  = get_env("VERTEX_AI_LOCATION", "us-central1")
```

### Chat — `app/tools/vertex_chat.py`

Send messages to Vertex Gemini with optional RAG retrieval. The system prompt can be read and modified at runtime.

```python
from tools.vertex_chat import run_chat, get_system_prompt, set_system_prompt, reset_system_prompt

# Read the current system prompt
print(get_system_prompt())

# Replace the system prompt (takes effect on next run_chat call)
set_system_prompt("You are a helpful cooking assistant.")

# Send a message (with optional conversation history)
result = run_chat("What is protein?", history=[
    {"role": "user", "content": "Hi"},
    {"role": "model", "content": "Hello!"},
])
print(result["reply"])   # model response
print(result["error"])   # empty string on success

# Restore the built-in default prompt
reset_system_prompt()
```

### RAG file management — `app/tools/rag_files.py`

List, import, and delete files in the Vertex RAG corpus (vector store).

```python
from tools.rag_files import list_files, import_files, delete_file

# List all files in the corpus
for f in list_files():
    print(f.display_name, f.name)

# Import files from GCS or Google Drive
result = import_files(["gs://my-bucket/doc.pdf", "https://drive.google.com/file/123"])
print(f"Imported {result.imported_count} file(s)")

# Delete a file by its full resource name
delete_file("projects/my-proj/locations/us-central1/ragCorpora/111/ragFiles/222")
```

### Cloud Storage uploads — `app/tools/gcs_storage.py`

Upload, list, and delete files in the GCS bucket set by `GCS_BUCKET`.

```python
from tools.gcs_storage import upload_file, upload_from_string, list_files, delete_file

# Upload a local file (returns gs:// URI)
uri = upload_file("/tmp/menu.pdf", destination_name="docs/menu.pdf")

# Upload raw bytes / string directly
uri = upload_from_string(b"hello world", "notes/greeting.txt", content_type="text/plain")

# List objects (optionally filtered by prefix)
for name in list_files(prefix="docs/"):
    print(name)

# Delete an object
delete_file("docs/menu.pdf")
```

A `.env.example` file is included at the repo root with every required and optional variable.

### Running tests

From the `app/` directory:

```bash
pip install pytest          # one-time
python -m pytest tools/tests.py -v
```

All Vertex AI calls are mocked — **no GCP credentials or network access needed** for CI.

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
| `app/tools/` | Vertex AI toolkit (env config, chat, RAG files, GCS storage, tests) |
| `.env.example` | Template listing all required / optional env vars |
| `Dockerfile` | Image for Gunicorn + WhiteNoise |
| `infrastructure/` | CDK TypeScript (`lib/config/`, `lib/constructs/`) |
