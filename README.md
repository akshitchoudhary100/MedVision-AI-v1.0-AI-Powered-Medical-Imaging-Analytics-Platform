# 🫁 Pneumonia Detection System
### Deep Learning · FastAPI · SQL Server · Streamlit

A production-ready chest X-ray classification pipeline that runs three trained deep learning models (CNN, ResNet50, EfficientNetB0) through a REST API, persists every prediction into a SQL Server data warehouse, and surfaces live analytics through a Streamlit dashboard — all in a single-command workflow.

---

## Why This Exists

Pneumonia kills over **2.5 million people a year** — and misdiagnosis or delayed diagnosis is one of the leading reasons. Radiologists in under-resourced hospitals often review hundreds of X-rays per shift. This tool is built to be a **second opinion at scale**: fast, auditable, and explainable.

---

## Architecture

```
[Chest X-Ray Image]
        │
        ▼
  ┌─────────────┐        POST /predict
  │  Streamlit  │ ──────────────────────► ┌───────────────────┐
  │  Frontend   │                         │  FastAPI Backend  │
  │  (app.py)   │ ◄──────────────────────  │   (main.py)       │
  └─────────────┘     JSON Response       └────────┬──────────┘
                                                   │
                                       ┌───────────▼──────────┐
                                       │  Model Inference      │
                                       │  CNN / ResNet50 /     │
                                       │  EfficientNetB0       │
                                       └───────────┬──────────┘
                                                   │
                                       ┌───────────▼──────────┐
                                       │  SQL Server Warehouse │
                                       │  Bronze → Silver →    │
                                       │  Gold (Views)         │
                                       └──────────────────────┘
```

---

## Features

- **3 model choices** — CNN (fast), ResNet50 (balanced), EfficientNetB0 (accurate)
- **Model-specific preprocessing** — each model gets the preprocessing it was trained with
- **Medallion data warehouse** — Bronze (raw), Silver (cleaned), Gold (analytical views)
- **Real-time analytics** — total scans, pneumonia rate, average confidence, latency
- **Full prediction history** — every inference stored with timestamp, confidence, image size
- **Swagger docs** — auto-generated at `/docs`
- **CORS-enabled** — ready to connect any frontend or external service

---

## Project Structure

```
pneumonia-detection/
│
├── main.py              # FastAPI backend — inference + DB + REST endpoints
├── app.py               # Streamlit frontend — upload, predict, dashboard
├── schema.sql           # SQL Server DDL — tables + 4 analytical views
│
└── model/
    ├── cnn_v1.h5
    ├── resnet50_v1.keras
    └── efficientnet_v1.keras
```

---

## Prerequisites

| Requirement         | Version       |
|---------------------|---------------|
| Python              | 3.9+          |
| SQL Server          | 2019+         |
| ODBC Driver         | 17            |
| TensorFlow          | 2.x           |

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/pneumonia-detection.git
cd pneumonia-detection

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install fastapi uvicorn tensorflow pillow numpy pyodbc streamlit requests

# 4. Set up the database — connect to SQL Server and run:
sqlcmd -S localhost,1433 -U sa -P StrongPass@123 -d modelDB -i schema.sql

# 5. Place your trained models in the model/ directory
#    model/cnn_v1.h5
#    model/resnet50_v1.keras
#    model/efficientnet_v1.keras
```

---

## Running the Application

Open **two terminals**:

```bash
# Terminal 1 — Start the FastAPI backend
uvicorn main:app --reload --port 8000

# Terminal 2 — Start the Streamlit frontend
streamlit run app.py
```

Then open your browser:

| Service         | URL                          |
|-----------------|------------------------------|
| Streamlit UI    | http://localhost:8501        |
| FastAPI Swagger | http://localhost:8000/docs   |
| Health Check    | http://localhost:8000/health |

---

## API Reference

### `POST /predict`
Upload a chest X-ray and receive a classification.

**Form fields:**
| Field        | Type   | Default | Options                           |
|--------------|--------|---------|-----------------------------------|
| `file`       | File   | —       | JPG, PNG                          |
| `model_name` | string | `cnn`   | `cnn`, `resnet50`, `efficientnet` |

**Response:**
```json
{
  "prediction_id": "3f2e1a...",
  "prediction":    "PNEUMONIA",
  "confidence":    94.27,
  "processing_ms": 312.5
}
```

---

### `GET /analytics`
Aggregate stats across all predictions.

```json
{
  "total_scans":     1024,
  "total_pneumonia": 612,
  "total_normal":    412,
  "avg_confidence":  89.4,
  "avg_latency_ms":  287.0
}
```

---

### `GET /history?limit=20`
Last N predictions, newest first.

---

### `GET /health`
Returns API status and available models.

---

## Database Schema

### `fact_predictions` (Silver Layer)
| Column           | Type          | Description                  |
|------------------|---------------|------------------------------|
| `prediction_id`  | NVARCHAR(36)  | UUID primary key             |
| `timestamp`      | DATETIME2     | Auto-set on insert           |
| `result`         | NVARCHAR(20)  | `PNEUMONIA` or `NORMAL`      |
| `confidence_pct` | DECIMAL(5,2)  | 0.00 – 100.00                |
| `processing_ms`  | INT           | End-to-end inference time    |
| `image_size_kb`  | FLOAT         | Uploaded image size          |
| `model_version`  | NVARCHAR(20)  | Model identifier             |

### Gold Layer Views

| View                          | Purpose                                 |
|-------------------------------|-----------------------------------------|
| `vw_daily_stats`              | Per-day scan counts, rates, latency     |
| `vw_summary`                  | All-time aggregate KPIs                 |
| `vw_weekly_trend`             | Week-over-week volume and confidence    |
| `vw_confidence_distribution`  | Bucketed confidence by result class     |

---

## Model Details

| Model          | Architecture     | Input Size | Notes                              |
|----------------|------------------|------------|------------------------------------|
| `cnn`          | Custom CNN       | 224×224    | Fastest; good for quick screening  |
| `resnet50`     | ResNet-50        | 224×224    | Balanced accuracy / speed          |
| `efficientnet` | EfficientNet-B0  | 224×224    | Highest accuracy; recommended      |

Each model uses its own preprocessing pipeline. EfficientNet and ResNet50 use their Keras application-specific normalisation. The custom CNN uses simple `/255` scaling.

---

## Configuration

To change the database connection, edit `CONN_STR` in `main.py`:

```python
CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost,1433;"
    "DATABASE=modelDB;"
    "UID=sa;"
    "PWD=YourPasswordHere;"
    "TrustServerCertificate=yes;"
)
```

To point the Streamlit app at a remote API, edit `API_URL` in `app.py`:

```python
API_URL = "http://your-server-ip:8000"
```

---

## Dataset

Models were trained on the [Chest X-Ray Images (Pneumonia)](https://www.kaggle.com/datasets/paultimothymooney/chest-xray-pneumonia) dataset from Kaggle — 5,863 JPEG images across NORMAL and PNEUMONIA classes, sourced from Guangzhou Women and Children's Medical Center.

---

## License

MIT License — free to use, modify, and distribute.

---

## Disclaimer

This tool is built for **research and educational purposes**. It is not a certified medical device and must not replace professional clinical diagnosis. Always consult a qualified radiologist for medical decisions.
