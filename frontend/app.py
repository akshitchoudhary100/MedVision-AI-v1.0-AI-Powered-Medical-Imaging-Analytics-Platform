"""
🫁 Pneumonia Detection — Streamlit Frontend
Connects to FastAPI backend running on localhost:8000
"""

import streamlit as st
import requests
from PIL import Image
import io

# ============================================================
# CONFIG
# ============================================================

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Pneumonia Detector",
    page_icon="🫁",
    layout="wide",
)

# ============================================================
# HELPERS
# ============================================================

def api_get(endpoint: str):
    """GET request to FastAPI; returns parsed JSON or None."""
    try:
        r = requests.get(f"{API_URL}{endpoint}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach the API. Is `main.py` running on port 8000?")
        return None
    except Exception as e:
        st.error(f"❌ API error: {e}")
        return None


def api_predict(image_bytes: bytes, filename: str, model_name: str):
    """POST image to /predict; returns parsed JSON or None."""
    try:
        r = requests.post(
            f"{API_URL}/predict",
            files={"file": (filename, image_bytes, "image/jpeg")},
            data={"model_name": model_name},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot reach the API. Is `main.py` running on port 8000?")
        return None
    except Exception as e:
        st.error(f"❌ Prediction error: {e}")
        return None


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🫁 Pneumonia Detector")
page = st.sidebar.radio("Navigate", ["🔬 Predict", "📊 Analytics", "📋 History"])

model_choice = st.sidebar.selectbox(
    "Model",
    ["cnn", "resnet50", "efficientnet"],
    index=0,
)

# API health check in sidebar
health = api_get("/health")
if health:
    st.sidebar.success("API: Online ✅")
else:
    st.sidebar.error("API: Offline ❌")


# ============================================================
# PAGE — PREDICT
# ============================================================

if page == "🔬 Predict":
    st.title("🔬 Chest X-Ray Prediction")
    st.write("Upload a chest X-ray image and the model will classify it.")

    uploaded = st.file_uploader(
        "Upload X-Ray (JPG / PNG)", type=["jpg", "jpeg", "png"]
    )

    if uploaded:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Uploaded Image")
            image = Image.open(uploaded).convert("RGB")
            st.image(image, use_column_width=True)
            st.caption(f"File: `{uploaded.name}` | "
                       f"Size: `{round(uploaded.size / 1024, 1)} KB`")

        with col2:
            st.subheader("Result")
            if st.button("🚀 Run Prediction", use_container_width=True):
                with st.spinner("Analysing image..."):
                    uploaded.seek(0)
                    result = api_predict(uploaded.read(), uploaded.name, model_choice)

                if result:
                    pred  = result["prediction"]
                    conf  = result["confidence"]
                    ms    = result["processing_ms"]
                    pid   = result["prediction_id"]

                    if pred == "PNEUMONIA":
                        st.error(f"### ⚠️ {pred}")
                    else:
                        st.success(f"### ✅ {pred}")

                    st.metric("Confidence",    f"{conf:.1f}%")
                    st.metric("Latency",       f"{ms:.0f} ms")
                    st.metric("Model used",    model_choice.upper())
                    st.caption(f"Prediction ID: `{pid}`")


# ============================================================
# PAGE — ANALYTICS
# ============================================================

elif page == "📊 Analytics":
    st.title("📊 Analytics Dashboard")

    data = api_get("/analytics")
    if data:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Scans",      data["total_scans"])
        col2.metric("Pneumonia Cases",  data["total_pneumonia"])
        col3.metric("Normal Cases",     data["total_normal"])
        col4.metric("Avg Confidence",   f"{data['avg_confidence']:.1f}%")
        col5.metric("Avg Latency",      f"{data['avg_latency_ms']:.0f} ms")

        total = data["total_scans"]
        if total > 0:
            st.subheader("Case Distribution")
            pneumonia_pct = round(100 * data["total_pneumonia"] / total, 1)
            normal_pct    = round(100 * data["total_normal"]    / total, 1)

            import pandas as pd
            chart_data = pd.DataFrame({
                "Category":   ["PNEUMONIA", "NORMAL"],
                "Percentage": [pneumonia_pct, normal_pct],
            }).set_index("Category")
            st.bar_chart(chart_data)


# ============================================================
# PAGE — HISTORY
# ============================================================

elif page == "📋 History":
    st.title("📋 Recent Predictions")

    rows = api_get("/history?limit=20")
    if rows is not None:
        if not rows:
            st.info("No predictions yet. Run one from the Predict page!")
        else:
            import pandas as pd
            df = pd.DataFrame(rows)
            df["result"] = df["result"].apply(
                lambda x: f"⚠️ {x}" if x == "PNEUMONIA" else f"✅ {x}"
            )
            st.dataframe(df, use_container_width=True)