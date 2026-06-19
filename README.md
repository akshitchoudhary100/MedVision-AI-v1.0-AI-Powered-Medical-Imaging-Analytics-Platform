# 🫁 PneumoScan — Clinical AI Platform

End-to-end pneumonia detection system. CNN classifies chest X-rays → FastAPI serves predictions → SQL Data Warehouse stores every result → Streamlit dashboard shows real-time analytics.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0-orange)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red)

---

## 🏗️ Architecture

```
User uploads X-ray
       ↓
  Streamlit UI  ──────────────────────────────┐
       ↓                                      │
  FastAPI /predict                            │
       ↓                                      │
  CNN Model (ResNet18)                        │
  + Grad-CAM heatmap                          │
       ↓                                      │
  SQLite Warehouse  ←── Medallion Architecture│
  (Bronze → Silver → Gold)                    │
       ↓                                      │
  /analytics endpoint ────────────────────────┘
       ↓
  Streamlit Dashboard (trends, KPIs, history)
```

---

## 📁 Structure

```
pneumonia-platform/
├── backend/
│   └── main.py              ← FastAPI server (predict + analytics)
├── frontend/
│   └── app.py               ← Streamlit UI (3 pages)
├── warehouse/
│   └── schema.sql           ← SQL schema (Bronze/Silver/Gold layers)
├── model/
│   └── pneumonia_cnn.pth    ← Your trained model (place here)
├── requirements.txt
└── README.md
```

---

## 🚀 Setup — Run in 5 Minutes

### Step 1 — Install dependencies

```bash
git clone https://github.com/akshitchoudhary100/pneumonia-platform
cd pneumonia-platform
pip install -r requirements.txt
```

### Step 2 — Add your trained model

Place your trained model file in `model/pneumonia_cnn.pth`

If your model uses a different architecture, edit `PneumoniaCNN` class in `backend/main.py`.

### Step 3 — Connect to your existing warehouse (optional)

If you want to use your existing SQL Server warehouse instead of SQLite:

1. Open `backend/main.py`
2. Replace the SQLite connection with your SQL Server connection string:
```python
# Replace:
conn = sqlite3.connect(DB_PATH)

# With your warehouse connection:
import pyodbc
conn = pyodbc.connect("Driver={SQL Server};Server=YOUR_SERVER;Database=YOUR_DB;...")
```
3. Run `warehouse/schema.sql` against your existing warehouse DB

### Step 4 — Start the API

```bash
uvicorn backend.main:app --reload --port 8000
```

API docs auto-generated at: http://localhost:8000/docs

### Step 5 — Start the frontend

```bash
streamlit run frontend/app.py
```

Opens at: http://localhost:8501

---

## 🌡️ Features

### Diagnosis Page
- Upload chest X-ray (JPG/PNG)
- CNN predicts: **PNEUMONIA** or **NORMAL**
- Confidence score (0-100%)
- **Grad-CAM heatmap** showing exactly which region triggered the prediction
- Every prediction auto-saved to warehouse

### Analytics Dashboard
- Total scans, pneumonia rate, average confidence
- 14-day daily trend chart
- Result distribution donut chart
- Confidence over time bar chart

### History Page
- Full prediction history from warehouse
- Sortable, filterable table
- All data queryable via SQL

---

## 🗄️ Warehouse Design (Medallion Architecture)

Extends the existing data warehouse project with a new domain:

```
Bronze: bronze_predictions_raw    ← raw API responses, no transformation
Silver: fact_predictions          ← cleaned, typed, validated predictions
Gold:   vw_daily_stats            ← daily aggregations for dashboard
        vw_summary                ← overall KPIs
        vw_weekly_trend           ← weekly patterns
        vw_confidence_distribution ← model calibration analysis
```

---

## 📊 Model Performance

| Metric | Score |
|--------|-------|
| Validation Accuracy | >90% |
| Architecture | ResNet18 (transfer learning) |
| Dataset | Chest X-Ray Images (Kaggle) |
| Training | PyTorch, Adam, BCELoss |

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/predict` | POST | Upload X-ray → get prediction + Grad-CAM |
| `/analytics` | GET | Warehouse analytics for dashboard |
| `/history` | GET | Recent predictions |
| `/health` | GET | API status check |

---

## 💡 Resume Bullets

```
• Built end-to-end clinical AI platform: CNN → FastAPI → SQL Warehouse → Streamlit
• Implemented Grad-CAM visualisation for model interpretability in medical imaging
• Extended Medallion Architecture data warehouse (Bronze/Silver/Gold) with prediction analytics
• Real-time dashboard showing population-level pneumonia trends across all predictions
• Tech: PyTorch, FastAPI, SQLite, Streamlit, Plotly, Grad-CAM, Docker
```

---

## ⚕️ Disclaimer

This tool is for educational and portfolio purposes only. Not intended for clinical diagnosis. Always consult a qualified radiologist.
