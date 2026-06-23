<div align="center">

# 📄 DocuFlow — Serverless Document Processing Pipeline

**Event-driven OCR & metadata extraction on Google Cloud Platform**

![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-black?logo=flask)
![GCP](https://img.shields.io/badge/Google_Cloud-4285F4?logo=google-cloud&logoColor=white)
![Cloud Run](https://img.shields.io/badge/Cloud_Run-4285F4?logo=google-cloud-run&logoColor=white)
![Pub/Sub](https://img.shields.io/badge/Pub%2FSub-FF6F00?logo=google-cloud&logoColor=white)
![BigQuery](https://img.shields.io/badge/BigQuery-669DF6?logo=google-bigquery&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
[![CI](https://github.com/derosavage/google-cloud-serverless-app/actions/workflows/ci.yml/badge.svg)](https://github.com/derosavage/google-cloud-serverless-app/actions/workflows/ci.yml)

</div>

---

## 🚀 Overview

A fully serverless, event-driven document processing pipeline that:

1. **Ingests** files uploaded to a **Google Cloud Storage** (GCS) bucket
2. **Triggers** via a **Pub/Sub** notification on object finalization
3. **Processes** documents with a **Flask** service deployed on **Cloud Run** — performing simulated OCR (word count, keyword extraction, tag generation)
4. **Streams** metadata directly into **BigQuery** for real-time querying and visualization

---

## 🧱 Architecture

```
┌──────────────┐     GCS Notif      ┌──────────────┐     Push Sub      ┌──────────────────┐
│   GCS Bucket │ ──────────────────▶ │  Pub/Sub     │ ──────────────────▶│  Cloud Run       │
│ (upload.pdf) │                    │  Topic        │                    │  (Flask App)     │
└──────────────┘                    └──────────────┘                    └────────┬─────────┘
                                                                                  │
                                                                                  ▼
                                                                         ┌──────────────────┐
                                                                         │   BigQuery       │
                                                                         │  (Metadata)      │
                                                                         └──────────────────┘
```

---

## 📁 Project Structure

```
├── src/
│   ├── __init__.py          # Package initializer
│   ├── app.py               # Flask application (Pub/Sub handler, REST API, Dashboard)
│   ├── ocr.py               # Document processing & keyword extraction logic
│   ├── requirements.txt     # Python dependencies
│   └── templates/
│       └── dashboard.html   # Real-time monitoring dashboard UI
│
├── scripts/
│   ├── deploy.sh            # Bash deployment script (Linux/macOS)
│   ├── deploy.ps1           # PowerShell deployment script (Windows)
│   ├── schema.json          # BigQuery table schema definition
│   ├── test_local.py        # Local integration test harness
│   └── test_cloud.py        # End-to-end cloud pipeline test
│
├── tests/
│   ├── __init__.py          # Test package initializer
│   └── test_ocr.py          # Unit tests for OCR module
│
├── .env.example             # Environment variable reference
├── .gitignore               # Git ignore rules
├── Dockerfile               # Container image for Cloud Run
├── LICENSE                  # MIT License
├── pyproject.toml           # Project metadata & build config
└── README.md                # This file
```

---

## 🧪 Local Development

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r src/requirements.txt

# Install dev dependencies (optional)
pip install -e ".[dev]"
```

### 2. Run Unit Tests

```bash
python -m unittest discover -s tests -v
```

### 3. Start the Flask Server

```bash
python src/app.py
```

The server starts at **`http://localhost:8080`** in mock mode (no GCP credentials required).

### 4. Simulate Document Uploads

With the server running, in another terminal:

```bash
python scripts/test_local.py
```

This sends mock Pub/Sub payloads to test text files, binary images, and ignored event types.

You can also use the **Upload Simulator** sidebar in the web dashboard at `http://localhost:8080`.

---

## ☁️ Deployment to GCP

### Prerequisites

- [Google Cloud CLI](https://cloud.google.com/sdk/gcloud) installed and configured
- Active GCP project with billing enabled
- Required APIs will be enabled automatically by the deployment script

### Quick Deploy

**PowerShell (Windows):**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\deploy.ps1
```

**Bash (Linux/macOS):**
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### What the Deployment Script Does

1. ✅ Enables required APIs (Storage, Pub/Sub, Cloud Run, BigQuery, Artifact Registry, Cloud Build)
2. ✅ Creates a GCS bucket named `<PROJECT_ID>-document-ingestion`
3. ✅ Creates a Pub/Sub topic `document-uploads-topic`
4. ✅ Grants GCS service account publisher permissions on the topic
5. ✅ Configures bucket notifications to Pub/Sub
6. ✅ Creates BigQuery dataset `document_pipeline` and table `processed_metadata`
7. ✅ Builds & deploys the Flask app to Cloud Run
8. ✅ Creates a push subscription targeting the Cloud Run endpoint

### Verify Deployment

Run the end-to-end cloud integration test:

```bash
python scripts/test_cloud.py
```

This uploads a test file, waits for processing, and verifies the metadata appears in BigQuery.

---

## 📊 Dashboard

The web UI at `https://<SERVICE-URL>/` provides:

- **Real-time stats**: file count, total words, unique tags, connection mode
- **Document table**: sortable, filterable view of all processed files
- **Tag filtering**: click any tag to filter documents
- **Search**: search by filename
- **Upload simulator**: trigger mock uploads directly from the browser
- **Detail modal**: click any document to view full metadata and OCR preview

---

## 🧪 Running Tests

| Test Suite | Command | Description |
|---|---|---|
| Unit tests | `python -m unittest discover -s tests` | OCR logic verification |
| Local integration | `python scripts/test_local.py` | Mock Pub/Sub → Flask handler |
| Cloud integration | `python scripts/test_cloud.py` | GCS → Pub/Sub → Cloud Run → BQ |

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| **Runtime** | Python 3.11+ |
| **Web Framework** | Flask 3.0 |
| **Compute** | Cloud Run (serverless containers) |
| **Storage** | Cloud Storage (GCS) |
| **Messaging** | Pub/Sub (push subscriptions) |
| **Data Warehouse** | BigQuery |
| **Containerization** | Docker |
| **Deployment** | gcloud CLI / Cloud Build |

---

## 🐛 Known Limitations

- OCR simulation uses keyword matching — not actual image recognition
- Mock mode requires no GCP credentials but stores data in memory (lost on restart)
- BigQuery streaming writes may have up to ~90 second propagation delay

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request