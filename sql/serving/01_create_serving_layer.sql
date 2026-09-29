-- ============================================================
-- Azure Transaction Risk Platform
-- Day 8 - Synapse Serverless Serving Layer
--
-- Database:
--   transaction_risk_serving
--
-- Schema:
--   serving
--
-- Purpose:
--   Expose Gold ML and DQ outputs through stable SQL views
--   for Power BI and analyst consumption.
--
-- Architecture:
--   ADLS Gen2 Gold / Audit Parquet
--              |
--              v
--   Synapse Serverless SQL
--              |
--              v
--       Serving Views
--              |
--              v
--          Power BI
--
-- Notes:
--   - Serverless SQL reads Parquet directly from ADLS Gen2.
--   - No dedicated SQL pool is required.
--   - Views provide stable consumption contracts for BI.
--   - Isolation Forest metrics are stored as metric/value rows
--     and are reshaped into a single-row serving view.
-- ============================================================


-- ============================================================
-- 1. Transaction Investigation
-- Grain: one scored transaction
-- ============================================================

CREATE OR ALTER VIEW serving.vw_transaction_investigation
AS
SELECT
    -- Transaction identity / timing
    trans_num,
    event_id,
    event_time,
    ingestion_time,

    -- Customer / transaction context
    merchant,
    category,
    amt,
    first,
    last,
    gender,
    street,
    city,
    state,
    zip,
    dob,

    -- Original geographic features
    lat,
    long,
    city_pop,
    merch_lat,
    merch_long,

    -- Engineered model features
    transaction_hour,
    day_of_week,
    month,
    customer_age,
    distance_km,

    -- Ground truth
    is_fraud,

    -- Model outputs
    fraud_probability,
    predicted_fraud,
    risk_band,

    -- Model metadata
    model_threshold,
    model_version,

    -- Source metadata
    source

FROM OPENROWSET(
    BULK 'https://sttransactionbello.dfs.core.windows.net/synapse/gold/ml/scored_transactions/scored_transactions.parquet',
    FORMAT = 'PARQUET'
) AS scored;
GO


-- ============================================================
-- 2. Executive Overview
-- Grain: transaction date + state
-- ============================================================

CREATE OR ALTER VIEW serving.vw_executive_overview
AS
SELECT
    CAST(event_time AS date) AS transaction_date,
    state,

    COUNT_BIG(*) AS transaction_count,

    SUM(amt) AS transaction_value,

    SUM(
        CASE
            WHEN predicted_fraud = 1 THEN 1
            ELSE 0
        END
    ) AS flagged_transaction_count,

    SUM(
        CASE
            WHEN predicted_fraud = 1 THEN amt
            ELSE 0
        END
    ) AS flagged_transaction_value,

    AVG(fraud_probability) AS average_fraud_probability,

    SUM(
        CASE
            WHEN is_fraud = 1 THEN 1
            ELSE 0
        END
    ) AS actual_fraud_count

FROM OPENROWSET(
    BULK 'https://sttransactionbello.dfs.core.windows.net/synapse/gold/ml/scored_transactions/scored_transactions.parquet',
    FORMAT = 'PARQUET'
) AS scored

GROUP BY
    CAST(event_time AS date),
    state;
GO


-- ============================================================
-- 3. XGBoost Model Metrics
-- Grain: metric type + threshold
-- ============================================================

CREATE OR ALTER VIEW serving.vw_xgboost_metrics
AS
SELECT
    metric_type,
    threshold,
    roc_auc,
    pr_auc,
    precision,
    recall,
    true_positive,
    false_positive,
    false_negative,
    true_negative

FROM OPENROWSET(
    BULK 'https://sttransactionbello.dfs.core.windows.net/synapse/gold/ml/xgboost_metrics.parquet',
    FORMAT = 'PARQUET'
) AS metrics;
GO


-- ============================================================
-- 4. Global SHAP Feature Importance
-- Grain: one feature
--
-- Note:
--   This artifact contains global mean absolute SHAP values.
--   It does not provide row-level/local explanations.
-- ============================================================

CREATE OR ALTER VIEW serving.vw_shap_feature_importance
AS
SELECT
    feature,
    mean_absolute_shap,
    rank

FROM OPENROWSET(
    BULK 'https://sttransactionbello.dfs.core.windows.net/synapse/gold/ml/shap_feature_importance.parquet',
    FORMAT = 'PARQUET'
) AS shap;
GO


-- ============================================================
-- 5. Isolation Forest Metrics
-- Grain: model evaluation
--
-- Gold artifact structure:
--   metric | value
--
-- The serving view reshapes these metric/value rows into
-- a single record for BI consumption.
-- ============================================================

CREATE OR ALTER VIEW serving.vw_isolation_forest_metrics
AS
SELECT
    MAX(
        CASE
            WHEN metric = 'roc_auc'
            THEN TRY_CAST(value AS FLOAT)
        END
    ) AS roc_auc,

    MAX(
        CASE
            WHEN metric = 'pr_auc'
            THEN TRY_CAST(value AS FLOAT)
        END
    ) AS pr_auc,

    MAX(
        CASE
            WHEN metric = 'evaluation_rows'
            THEN TRY_CAST(value AS BIGINT)
        END
    ) AS evaluation_rows,

    MAX(
        CASE
            WHEN metric = 'anomalies_detected'
            THEN TRY_CAST(value AS BIGINT)
        END
    ) AS anomalies_detected,

    MAX(
        CASE
            WHEN metric = 'normal_transactions'
            THEN TRY_CAST(value AS BIGINT)
        END
    ) AS normal_transactions,

    MAX(
        CASE
            WHEN metric = 'anomaly_rate'
            THEN TRY_CAST(value AS FLOAT)
        END
    ) AS anomaly_rate,

    MAX(
        CASE
            WHEN metric = 'normal_group_fraud_rate'
            THEN TRY_CAST(value AS FLOAT)
        END
    ) AS normal_group_fraud_rate,

    MAX(
        CASE
            WHEN metric = 'anomaly_group_fraud_rate'
            THEN TRY_CAST(value AS FLOAT)
        END
    ) AS anomaly_group_fraud_rate

FROM OPENROWSET(
    BULK 'https://sttransactionbello.dfs.core.windows.net/synapse/gold/ml/isolation_forest_metrics.parquet',
    FORMAT = 'PARQUET'
) AS metrics;
GO


-- ============================================================
-- 6. Pipeline / Data Quality Health
-- Grain: pipeline run
-- ============================================================

CREATE OR ALTER VIEW serving.vw_pipeline_health
AS
SELECT
    run_time,
    rows_received,
    rows_valid,
    rows_quarantined,
    duplicate_rows,
    duplicate_rate,
    dq_pass_rate

FROM OPENROWSET(
    BULK 'https://sttransactionbello.dfs.core.windows.net/synapse/audit/dq_metrics/run_date=2026-09-28/dq_metrics.parquet',
    FORMAT = 'PARQUET'
) AS dq;
GO


-- ============================================================
-- Validation queries
-- ============================================================

-- Transaction investigation
SELECT TOP 5 *
FROM serving.vw_transaction_investigation;


-- Executive overview
SELECT *
FROM serving.vw_executive_overview;


-- XGBoost metrics
SELECT *
FROM serving.vw_xgboost_metrics;


-- Global SHAP feature importance
SELECT *
FROM serving.vw_shap_feature_importance
ORDER BY rank;


-- Isolation Forest metrics
SELECT *
FROM serving.vw_isolation_forest_metrics;


-- Pipeline / DQ health
SELECT *
FROM serving.vw_pipeline_health;
