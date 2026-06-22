-- ============================================================
-- 🫁 PNEUMONIA DETECTION — Data Warehouse Schema (SQL Server)
-- ============================================================
-- Run this once on a fresh DB, OR run the ALTER section below
-- if fact_predictions already exists from a previous version.
-- ============================================================


-- ── BRONZE LAYER — Raw ingestion log ────────────────────────

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'bronze_predictions_raw' AND xtype = 'U')
BEGIN
    CREATE TABLE bronze_predictions_raw (
        raw_id          NVARCHAR(100)   PRIMARY KEY,
        received_at     NVARCHAR(50)    NOT NULL,
        image_filename  NVARCHAR(255),
        image_size_kb   FLOAT,
        raw_response    NVARCHAR(MAX)
    );
END;


-- ── SILVER LAYER — fact_predictions ─────────────────────────
-- main.py also creates this table on startup (idempotent).

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'fact_predictions' AND xtype = 'U')
BEGIN
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
    );
END;


-- ── MIGRATION — add model_name if upgrading from old schema ──
-- Safe to run even if column already exists (checks first).

IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'fact_predictions' AND COLUMN_NAME = 'model_name'
)
BEGIN
    ALTER TABLE fact_predictions
    ADD model_name NVARCHAR(30) NOT NULL DEFAULT 'cnn';
END;


-- ── GOLD LAYER — Views ───────────────────────────────────────
-- All views are dropped and recreated so changes always apply.


-- 1. Daily stats (existing — kept for backward compat)
IF OBJECT_ID('vw_daily_stats', 'V') IS NOT NULL DROP VIEW vw_daily_stats;
GO
CREATE VIEW vw_daily_stats AS
SELECT
    CAST(timestamp AS DATE)                                                 AS prediction_date,
    COUNT(*)                                                                AS total_scans,
    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)                  AS pneumonia_cases,
    SUM(CASE WHEN result = 'NORMAL'    THEN 1 ELSE 0 END)                  AS normal_cases,
    ROUND(100.0 * SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                                    AS pneumonia_rate_pct,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                           AS avg_confidence,
    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)                           AS avg_latency_ms,
    MIN(processing_ms)                                                      AS min_latency_ms,
    MAX(processing_ms)                                                      AS max_latency_ms
FROM fact_predictions
GROUP BY CAST(timestamp AS DATE);
GO


-- 2. Overall summary (existing — kept for backward compat)
IF OBJECT_ID('vw_summary', 'V') IS NOT NULL DROP VIEW vw_summary;
GO
CREATE VIEW vw_summary AS
SELECT
    COUNT(*)                                                                AS total_scans,
    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)                  AS total_pneumonia,
    SUM(CASE WHEN result = 'NORMAL'    THEN 1 ELSE 0 END)                  AS total_normal,
    ROUND(100.0 * SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                                    AS pneumonia_rate_pct,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                           AS avg_confidence,
    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)                           AS avg_latency_ms,
    COUNT(DISTINCT CAST(timestamp AS DATE))                                 AS active_days,
    MIN(timestamp)                                                          AS first_prediction,
    MAX(timestamp)                                                          AS last_prediction
FROM fact_predictions;
GO


-- 3. Weekly trend (existing — kept for backward compat)
IF OBJECT_ID('vw_weekly_trend', 'V') IS NOT NULL DROP VIEW vw_weekly_trend;
GO
CREATE VIEW vw_weekly_trend AS
SELECT
    FORMAT(timestamp, 'yyyy-ww')                                            AS week,
    COUNT(*)                                                                AS total_scans,
    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)                  AS pneumonia_cases,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                           AS avg_confidence
FROM fact_predictions
GROUP BY FORMAT(timestamp, 'yyyy-ww');
GO


-- 4. Confidence distribution (existing — kept for backward compat)
IF OBJECT_ID('vw_confidence_distribution', 'V') IS NOT NULL DROP VIEW vw_confidence_distribution;
GO
CREATE VIEW vw_confidence_distribution AS
SELECT
    CASE
        WHEN confidence_pct >= 90 THEN '90-100%'
        WHEN confidence_pct >= 80 THEN '80-90%'
        WHEN confidence_pct >= 70 THEN '70-80%'
        WHEN confidence_pct >= 60 THEN '60-70%'
        ELSE                           '50-60%'
    END                                                                     AS confidence_bucket,
    result,
    COUNT(*)                                                                AS scan_count
FROM fact_predictions
GROUP BY
    CASE
        WHEN confidence_pct >= 90 THEN '90-100%'
        WHEN confidence_pct >= 80 THEN '80-90%'
        WHEN confidence_pct >= 70 THEN '70-80%'
        WHEN confidence_pct >= 60 THEN '60-70%'
        ELSE                           '50-60%'
    END,
    result;
GO


-- ★ 5. Per-model performance breakdown — NEW
IF OBJECT_ID('vw_model_performance', 'V') IS NOT NULL DROP VIEW vw_model_performance;
GO
CREATE VIEW vw_model_performance AS
SELECT
    model_name,
    COUNT(*)                                                                AS total_scans,
    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)                  AS pneumonia_cases,
    SUM(CASE WHEN result = 'NORMAL'    THEN 1 ELSE 0 END)                  AS normal_cases,
    ROUND(100.0 * SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)
          / COUNT(*), 2)                                                    AS pneumonia_rate_pct,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                           AS avg_confidence_pct,
    ROUND(MIN(CAST(confidence_pct AS FLOAT)), 2)                           AS min_confidence_pct,
    ROUND(MAX(CAST(confidence_pct AS FLOAT)), 2)                           AS max_confidence_pct,
    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)                           AS avg_latency_ms,
    MIN(processing_ms)                                                      AS min_latency_ms,
    MAX(processing_ms)                                                      AS max_latency_ms
FROM fact_predictions
GROUP BY model_name;
GO


-- ★ 6. Model summary — head-to-head comparison card — NEW
IF OBJECT_ID('vw_model_summary', 'V') IS NOT NULL DROP VIEW vw_model_summary;
GO
CREATE VIEW vw_model_summary AS
SELECT
    model_name,
    COUNT(*)                                                                AS total_scans,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                           AS avg_confidence_pct,
    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)                           AS avg_latency_ms,
    -- Reliability score: high confidence + low latency = better score
    ROUND(
        AVG(CAST(confidence_pct AS FLOAT))
        - (AVG(CAST(processing_ms AS FLOAT)) / 100.0),
        2
    )                                                                       AS reliability_score,
    MIN(timestamp)                                                          AS first_used,
    MAX(timestamp)                                                          AS last_used
FROM fact_predictions
GROUP BY model_name;
GO


-- ★ 7. Recent 20 predictions with model name — what recruiters want to see
IF OBJECT_ID('vw_recent_predictions', 'V') IS NOT NULL DROP VIEW vw_recent_predictions;
GO
CREATE VIEW vw_recent_predictions AS
SELECT TOP 20
    prediction_id,
    FORMAT(timestamp, 'yyyy-MM-dd HH:mm:ss')                               AS scan_time,
    model_name,
    result,
    confidence_pct,
    processing_ms,
    image_size_kb
FROM fact_predictions
ORDER BY timestamp DESC;
GO

-- Head-to-head model comparison (the money shot)
SELECT * FROM vw_model_performance;

-- Reliability ranking
SELECT * FROM vw_model_summary ORDER BY reliability_score DESC;

-- Recent predictions with model name visible
SELECT * FROM vw_recent_predictions;

-- Total scan count
SELECT COUNT(*) AS total_scans FROM fact_predictions;

-- Confidence distribution per model
SELECT model_name, confidence_bucket, scan_count
FROM vw_confidence_distribution cd
JOIN fact_predictions fp ON 1=1
GROUP BY model_name, confidence_bucket, scan_count;