-- ============================================================
-- 🫁 PNEUMONIA DETECTION — Data Warehouse Schema (SQL Server)
-- ============================================================
-- Run this once to set up all tables and views.
-- main.py also creates fact_predictions on startup (idempotent).
-- ============================================================


-- ── BRONZE LAYER — Raw predictions ──────────────────────────

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


-- ── SILVER LAYER — Cleaned predictions ──────────────────────
-- NOTE: main.py also creates this table on startup (same definition).

IF NOT EXISTS (SELECT * FROM sysobjects WHERE name = 'fact_predictions' AND xtype = 'U')
BEGIN
    CREATE TABLE fact_predictions (
        prediction_id   NVARCHAR(36)    PRIMARY KEY,
        timestamp       DATETIME2       NOT NULL DEFAULT GETDATE(),
        result          NVARCHAR(20)    NOT NULL
                        CHECK (result IN ('PNEUMONIA', 'NORMAL')),
        confidence_pct  DECIMAL(5,2)    NOT NULL
                        CHECK (confidence_pct BETWEEN 0 AND 100),
        processing_ms   INT,
        image_size_kb   FLOAT,
        model_version   NVARCHAR(20)    DEFAULT 'v1.0'
    );
END;


-- ── GOLD LAYER — Analytical Views ───────────────────────────

-- Daily stats
IF OBJECT_ID('vw_daily_stats', 'V') IS NOT NULL
    DROP VIEW vw_daily_stats;
GO

CREATE VIEW vw_daily_stats AS
SELECT
    CAST(timestamp AS DATE)                                                         AS prediction_date,
    COUNT(*)                                                                        AS total_scans,
    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)                          AS pneumonia_cases,
    SUM(CASE WHEN result = 'NORMAL'    THEN 1 ELSE 0 END)                          AS normal_cases,
    ROUND(
        100.0 * SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END) / COUNT(*),
        2
    )                                                                               AS pneumonia_rate_pct,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                                   AS avg_confidence,
    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)                                   AS avg_latency_ms,
    MIN(processing_ms)                                                              AS min_latency_ms,
    MAX(processing_ms)                                                              AS max_latency_ms
FROM fact_predictions
GROUP BY CAST(timestamp AS DATE);
GO


-- Overall summary
IF OBJECT_ID('vw_summary', 'V') IS NOT NULL
    DROP VIEW vw_summary;
GO

CREATE VIEW vw_summary AS
SELECT
    COUNT(*)                                                                        AS total_scans,
    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)                          AS total_pneumonia,
    SUM(CASE WHEN result = 'NORMAL'    THEN 1 ELSE 0 END)                          AS total_normal,
    ROUND(
        100.0 * SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END) / COUNT(*),
        2
    )                                                                               AS pneumonia_rate_pct,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                                   AS avg_confidence,
    ROUND(AVG(CAST(processing_ms  AS FLOAT)), 0)                                   AS avg_latency_ms,
    COUNT(DISTINCT CAST(timestamp AS DATE))                                         AS active_days,
    MIN(timestamp)                                                                  AS first_prediction,
    MAX(timestamp)                                                                  AS last_prediction
FROM fact_predictions;
GO


-- Weekly trend
IF OBJECT_ID('vw_weekly_trend', 'V') IS NOT NULL
    DROP VIEW vw_weekly_trend;
GO

CREATE VIEW vw_weekly_trend AS
SELECT
    FORMAT(timestamp, 'yyyy-ww')                                                    AS week,
    COUNT(*)                                                                        AS total_scans,
    SUM(CASE WHEN result = 'PNEUMONIA' THEN 1 ELSE 0 END)                          AS pneumonia_cases,
    ROUND(AVG(CAST(confidence_pct AS FLOAT)), 2)                                   AS avg_confidence
FROM fact_predictions
GROUP BY FORMAT(timestamp, 'yyyy-ww');
GO


-- Confidence distribution
IF OBJECT_ID('vw_confidence_distribution', 'V') IS NOT NULL
    DROP VIEW vw_confidence_distribution;
GO

CREATE VIEW vw_confidence_distribution AS
SELECT
    CASE
        WHEN confidence_pct >= 90 THEN '90-100%'
        WHEN confidence_pct >= 80 THEN '80-90%'
        WHEN confidence_pct >= 70 THEN '70-80%'
        WHEN confidence_pct >= 60 THEN '60-70%'
        ELSE                           '50-60%'
    END                                                                             AS confidence_bucket,
    result,
    COUNT(*)                                                                        AS count
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
