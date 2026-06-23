"""
🫁 Pneumonia Detection API — FastAPI
CNN / ResNet50 / EfficientNetB0  +  SQL Server Warehouse  +  Streamlit Frontend
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.applications.efficientnet import preprocess_input as efficientnet_preprocess
from tensorflow.keras.applications.resnet50 import preprocess_input as resnet_preprocess

import numpy as np
from PIL import Image

import io
import uuid
import time
from contextlib import contextmanager

import pyodbc


# ============================================================
# APP SETUP
# ============================================================

app = FastAPI(title="Pneumonia Detection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# CONFIG
# ============================================================

IMAGE_SIZE = 224

CLASS_NAMES = ["NORMAL", "PNEUMONIA"]

MODEL_PATHS = {
    "cnn":          "model/cnn_v2.keras",
    "resnet50":     "model/resnet50_v1.keras",
    "efficientnet": "model/efficientnet_v1.keras",
}

# Each model gets the preprocessing it was trained with.
# CNN falls through to simple /255 scaling handled in preprocess_image().
PREPROCESS_MAP = {
    "efficientnet": efficientnet_preprocess,
    "resnet50":     resnet_preprocess,
}

loaded_models: dict = {}

CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost,1433;"
    "DATABASE=modelDB;"
    "UID=sa;"
    "PWD=StrongPass@123;"
    "TrustServerCertificate=yes;"
)


# ============================================================
# DATABASE
# ============================================================

@contextmanager
def get_db():
    """Yield a committed pyodbc connection; rollback on any error."""
    conn = pyodbc.connect(CONN_STR)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_warehouse():
    """
    Create fact_predictions on first run.
    Also adds model_name column if upgrading from the old schema
    (the column didn't exist in earlier versions of this project).
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()

            # Create table if it doesn't exist yet
            cur.execute("""
                IF NOT EXISTS (
                    SELECT * FROM sysobjects
                    WHERE name = 'fact_predictions' AND xtype = 'U'
                )
                CREATE TABLE fact_predictions (
                    prediction_id   NVARCHAR(36)    PRIMARY KEY,
                    timestamp       DATETIME2       NOT NULL DEFAULT GETDATE(),
                    model_name      NVARCHAR(30)    NOT NULL DEFAULT 'cnn',
                    result          NVARCHAR(20)    NOT NULL
                                    CHECK (result IN ('PNEUMONIA', 'NORMAL')),
                    confidence_pct  DECIMAL(5,2)    NOT NULL
                                    CHECK (confidence_pct BETWEEN 0 AND 100),
                    processing_ms   INT,
                    image_size_kb   FLOAT,
                    model_version   NVARCHAR(20)    DEFAULT 'v1.0'
                )
            """)

            # Migration: add model_name to tables created by the old schema
            cur.execute("""
                IF NOT EXISTS (
                    SELECT * FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = 'fact_predictions'
                    AND COLUMN_NAME = 'model_name'
                )
                ALTER TABLE fact_predictions
                ADD model_name NVARCHAR(30) NOT NULL DEFAULT 'cnn'
            """)

        print("✅ SQL Server connected — warehouse ready")
    except Exception as e:
        print(f"❌ Database init error: {e}")


def store_prediction(
    pid: str,
    model_name: str,
    result: str,
    confidence: float,
    ms: float,
    image_size_kb: float = None,
):
    """Persist one prediction row. confidence is 0-1 float; stored as 0-100."""
    try:
        with get_db() as conn:
            conn.cursor().execute("""
                INSERT INTO fact_predictions
                    (prediction_id, model_name, result,
                     confidence_pct, processing_ms, image_size_kb)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pid,
                model_name,
                result,
                round(confidence * 100, 2),
                int(ms),
                round(image_size_kb, 2) if image_size_kb else None,
            ))
    except Exception as e:
        print(f"❌ Insert error: {e}")


def get_analytics() -> dict:
    """Overall aggregate stats — used by /analytics and the Streamlit dashboard."""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN result = 'NORMAL'    THEN 1 ELSE 0 END),
                    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2),
                    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)
                FROM fact_predictions
            """)
            r = c.fetchone()
            return {
                "total_scans":     r[0] or 0,
                "total_pneumonia": r[1] or 0,
                "total_normal":    r[2] or 0,
                "avg_confidence":  float(r[3] or 0),
                "avg_latency_ms":  float(r[4] or 0),
            }
    except Exception as e:
        print(f"❌ Analytics error: {e}")
        return {
            "total_scans": 0, "total_pneumonia": 0, "total_normal": 0,
            "avg_confidence": 0, "avg_latency_ms": 0,
        }


def get_model_stats() -> list:
    """Per-model breakdown — powers the /model-stats endpoint."""
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT
                    model_name,
                    COUNT(*)                                                    AS total_scans,
                    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)               AS avg_confidence,
                    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)               AS avg_latency_ms,
                    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)      AS pneumonia_cases,
                    SUM(CASE WHEN result = 'NORMAL'    THEN 1 ELSE 0 END)      AS normal_cases
                FROM fact_predictions
                GROUP BY model_name
                ORDER BY total_scans DESC
            """)
            rows = c.fetchall()
            return [
                {
                    "model_name":      r[0],
                    "total_scans":     r[1],
                    "avg_confidence":  float(r[2] or 0),
                    "avg_latency_ms":  float(r[3] or 0),
                    "pneumonia_cases": r[4],
                    "normal_cases":    r[5],
                }
                for r in rows
            ]
    except Exception as e:
        print(f"❌ Model stats error: {e}")
        return []


# ============================================================
# MODEL HELPERS
# ============================================================

def get_model(model_name: str):
    """Load once from disk, then serve from memory cache."""
    if model_name in loaded_models:
        return loaded_models[model_name]

    path = MODEL_PATHS.get(model_name)
    if not path:
        raise ValueError(
            f"Unknown model '{model_name}'. Valid options: {list(MODEL_PATHS.keys())}"
        )

    model = keras.models.load_model(path)
    loaded_models[model_name] = model
    print(f"✅ Loaded model: {model_name}")
    return model


def preprocess_image(pil_image: Image.Image, model_name: str) -> np.ndarray:
    """
    Resize to 224×224 and apply the preprocessing each architecture expects.
    EfficientNet and ResNet50 have their own Keras preprocess_input functions.
    The custom CNN was trained with simple /255 normalisation — no extra steps.
    """
    img = pil_image.resize((IMAGE_SIZE, IMAGE_SIZE))
    arr = np.array(img).astype(np.float32)

    preprocess_fn = PREPROCESS_MAP.get(model_name)
    if preprocess_fn:
        arr = preprocess_fn(arr)
    else:
        arr = arr / 255.0

    return np.expand_dims(arr, axis=0)


# ============================================================
# STARTUP
# ============================================================

init_warehouse()


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def root():
    return {"status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {
        "api": "running",
        "available_models": list(MODEL_PATHS.keys()),
    }


@app.post("/predict")
async def predict(
    file: UploadFile = File(...),
    model_name: str = Form("cnn"),
):
    # ── Load model ───────────────────────────────────────────
    try:
        model = get_model(model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model load failed: {e}")

    start = time.time()

    # ── Read & decode image ───────────────────────────────────
    try:
        contents = await file.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or unreadable image file.")

    image_size_kb = len(contents) / 1024

    # ── Preprocess & infer ────────────────────────────────────
    img_array = preprocess_image(pil_image, model_name)
    prob = float(model.predict(img_array, verbose=0)[0][0])

    prediction = "PNEUMONIA" if prob >= 0.5 else "NORMAL"
    confidence = prob if prediction == "PNEUMONIA" else 1.0 - prob

    elapsed_ms = (time.time() - start) * 1000
    pid = str(uuid.uuid4())

    # ── Persist ───────────────────────────────────────────────
    store_prediction(
        pid=pid,
        model_name=model_name,        # ← now correctly stored per prediction
        result=prediction,
        confidence=confidence,
        ms=elapsed_ms,
        image_size_kb=image_size_kb,
    )

    return {
        "prediction_id": pid,
        "model_used":    model_name,
        "prediction":    prediction,
        "confidence":    round(confidence * 100, 2),
        "processing_ms": round(elapsed_ms, 2),
    }


@app.get("/analytics")
def analytics():
    return get_analytics()


@app.get("/model-stats")
def model_stats():
    """Per-model breakdown: scans, avg confidence, avg latency, case split."""
    return get_model_stats()


@app.get("/history")
def history(limit: int = 20):
    try:
        with get_db() as conn:
            c = conn.cursor()
            c.execute(f"""
                SELECT TOP {min(limit, 100)}
                    prediction_id,
                    timestamp,
                    model_name,
                    result,
                    confidence_pct,
                    processing_ms,
                    image_size_kb
                FROM fact_predictions
                ORDER BY timestamp DESC
            """)
            rows = c.fetchall()
            return [
                {
                    "prediction_id":  r[0],
                    "timestamp":      str(r[1]),
                    "model_name":     r[2],
                    "result":         r[3],
                    "confidence_pct": float(r[4]),
                    "processing_ms":  r[5],
                    "image_size_kb":  float(r[6]) if r[6] else None,
                }
                for r in rows
            ]
    except Exception as e:
        print(f"❌ History error: {e}")
        return []