"""Compare live API predictions with saved Gold predictions for real Silver rows."""

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project-root packages (such as src) are importable when this
# file is executed directly from the scripts directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pyarrow.parquet as pq
import requests

from src.model_store import get_adls_filesystem


SILVER_ROOT = "silver/transactions/streaming"
GOLD_PATH = "gold/ml/scored_transactions/scored_transactions.parquet"
FEATURE_INPUTS = [
    "event_time", "dob", "amt", "city_pop",
    "lat", "long", "merch_lat", "merch_long",
]
PREDICTION_FIELDS = [
    "fraud_probability", "predicted_fraud", "risk_band",
    "model_version", "threshold",
]


def read_adls_parquet(fs, path):
    """Download one Parquet file from ADLS and read it into a DataFrame."""
    raw = fs.get_file_client(path).download_file().readall()
    return pq.read_table(io.BytesIO(raw)).to_pandas()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    api_key = os.environ.get("API_KEY")
    if not api_key:
        sys.exit("ERROR: Set API_KEY in this terminal before running the script.")
    if args.sample_size < 1:
        sys.exit("ERROR: --sample-size must be at least 1.")

    output_dir = Path("docs/evidence/parity")
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {"X-API-Key": api_key}

    # 1. Confirm the API is reachable and inspect the loaded model.
    try:
        health = requests.get(f"{args.base_url}/health", timeout=10)
        health.raise_for_status()
        model_response = requests.get(
            f"{args.base_url}/model-info", headers=headers, timeout=10
        )
        model_response.raise_for_status()
        model_info = model_response.json()
    except requests.RequestException as exc:
        sys.exit(f"ERROR: Cannot reach the API or read model info: {exc}")

    expected_run_id = os.environ.get(
        "EXPECTED_MODEL_RUN_ID", "20261012T024013Z"
    )
    if model_info.get("model_run_id") != expected_run_id:
        sys.exit(
            "ERROR: API model run ID does not match the expected run. "
            f"Expected {expected_run_id!r}; got "
            f"{model_info.get('model_run_id')!r}. No replay was run."
        )

    print("API health: OK")
    print("API model version:", model_info.get("model_version"))
    print("API model run ID:", model_info.get("model_run_id"))
    print("API threshold:", model_info.get("threshold"))

    # 2. Read the real Silver streaming data and Gold predictions.
    print("\nReading Silver streaming Parquet files from ADLS...")
    fs = get_adls_filesystem("sttransactionbello", "synapse")
    silver_paths = sorted(
        item.name
        for item in fs.get_paths(path=SILVER_ROOT, recursive=True)
        if not item.is_directory and item.name.lower().endswith(".parquet")
    )
    if not silver_paths:
        sys.exit(f"ERROR: No Parquet files found under {SILVER_ROOT}")

    silver = pd.concat(
        [read_adls_parquet(fs, path) for path in silver_paths],
        ignore_index=True,
    )
    gold = read_adls_parquet(fs, GOLD_PATH)

    required_silver = {"event_id", *FEATURE_INPUTS}
    required_gold = {
        "event_id", "fraud_probability", "predicted_fraud",
        "risk_band", "model_threshold", "model_version",
    }
    if missing := required_silver - set(silver.columns):
        sys.exit(f"ERROR: Silver is missing columns: {sorted(missing)}")
    if missing := required_gold - set(gold.columns):
        sys.exit(f"ERROR: Gold is missing columns: {sorted(missing)}")

    if silver["event_id"].duplicated().any():
        sys.exit("ERROR: Silver contains duplicate event_id values.")
    if gold["event_id"].duplicated().any():
        sys.exit("ERROR: Gold contains duplicate event_id values.")

    # Gold has no model_run_id column. We can verify its version and threshold,
    # but cannot prove the exact training run from Gold alone.
    joined = silver.merge(
        gold[
            [
                "event_id", "fraud_probability", "predicted_fraud",
                "risk_band", "model_threshold", "model_version",
            ]
        ],
        on="event_id",
        how="inner",
        validate="one_to_one",
    )
    print(f"Silver rows: {len(silver):,}")
    print(f"Gold rows: {len(gold):,}")
    print(f"Matched event IDs: {len(joined):,}")
    print(f"Unmatched Silver IDs: {len(silver) - len(joined):,}")

    if joined.empty:
        sys.exit("ERROR: No matching event_id values between Silver and Gold.")

    if not (joined["model_version"] == model_info["model_version"]).all():
        sys.exit("ERROR: Gold and API model versions differ; replay stopped.")
    if not (
        (joined["model_threshold"] - float(model_info["threshold"])).abs()
        <= args.tolerance
    ).all():
        sys.exit("ERROR: Gold and API thresholds differ; replay stopped.")

    # 3. Sample across Gold risk bands, then fill any remaining slots.
    bands = sorted(joined["risk_band"].dropna().unique().tolist())
    per_band = max(1, args.sample_size // max(1, len(bands)))
    parts = []
    for band in bands:
        group = joined[joined["risk_band"] == band]
        parts.append(
            group.sample(
                n=min(per_band, len(group)),
                random_state=args.seed,
            )
        )
    sampled = pd.concat(parts).drop_duplicates("event_id")

    if len(sampled) < min(args.sample_size, len(joined)):
        remaining = joined[~joined["event_id"].isin(sampled["event_id"])]
        extra_count = min(args.sample_size - len(sampled), len(remaining))
        if extra_count:
            sampled = pd.concat(
                [
                    sampled,
                    remaining.sample(n=extra_count, random_state=args.seed),
                ]
            )

    sampled = sampled.head(args.sample_size)
    print(f"Selected for API replay: {len(sampled)}")
    print("Gold risk-band distribution:", sampled["risk_band"].value_counts().to_dict())

    # 4. Send raw fields to the API and compare the returned prediction.
    results = []
    for index, row in sampled.iterrows():
        payload = {
            "event_time": pd.Timestamp(row["event_time"]).isoformat(),
            "dob": pd.Timestamp(row["dob"]).isoformat(),
            "amt": float(row["amt"]),
            "city_pop": float(row["city_pop"]),
            "lat": float(row["lat"]),
            "long": float(row["long"]),
            "merch_lat": float(row["merch_lat"]),
            "merch_long": float(row["merch_long"]),
        }

        result = {
            "event_id": row["event_id"],
            "http_status": None,
            "error": "",
            "probability_abs_delta": None,
            "probability_match": False,
            "class_match": False,
            "risk_band_match": False,
            "model_version_match": False,
            "run_id_match": False,
            "threshold_match": False,
            "gold_probability": float(row["fraud_probability"]),
            "api_probability": None,
            "gold_predicted_fraud": int(row["predicted_fraud"]),
            "api_predicted_fraud": None,
            "gold_risk_band": str(row["risk_band"]),
            "api_risk_band": None,
            "gold_model_version": str(row["model_version"]),
            "api_model_version": None,
            "api_model_run_id": None,
            "gold_threshold": float(row["model_threshold"]),
            "api_threshold": None,
        }

        try:
            response = requests.post(
                f"{args.base_url}/predict",
                headers=headers,
                json=payload,
                timeout=30,
            )
            result["http_status"] = response.status_code
            response.raise_for_status()
            prediction = response.json()

            result["api_probability"] = float(prediction["fraud_probability"])
            result["probability_abs_delta"] = abs(
                result["api_probability"] - result["gold_probability"]
            )
            result["probability_match"] = (
                result["probability_abs_delta"] <= args.tolerance
            )

            result["api_predicted_fraud"] = int(prediction["predicted_fraud"])
            result["class_match"] = (
                result["api_predicted_fraud"] == result["gold_predicted_fraud"]
            )

            result["api_risk_band"] = str(prediction["risk_band"])
            result["risk_band_match"] = (
                result["api_risk_band"] == result["gold_risk_band"]
            )

            result["api_model_version"] = str(prediction["model_version"])
            result["model_version_match"] = (
                result["api_model_version"] == result["gold_model_version"]
            )

            result["api_model_run_id"] = str(prediction["model_run_id"])
            result["run_id_match"] = (
                result["api_model_run_id"] == expected_run_id
            )

            result["api_threshold"] = float(prediction["threshold"])
            result["threshold_match"] = (
                abs(result["api_threshold"] - result["gold_threshold"])
                <= args.tolerance
            )

        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            result["error"] = str(exc)[:300]

        results.append(result)
        if len(results) % 10 == 0 or len(results) == len(sampled):
            print(f"Replayed {len(results)}/{len(sampled)}")

    # 5. Save prediction-only evidence; no raw customer input fields are saved.
    details = pd.DataFrame(results)
    details_path = output_dir / "details.csv"
    mismatch_path = output_dir / "mismatches.csv"
    check_columns = [
        "probability_match", "class_match", "risk_band_match",
        "model_version_match", "run_id_match", "threshold_match",
    ]
    details["all_checks_pass"] = (
        details[check_columns].all(axis=1) & details["error"].eq("")
    )
    details.to_csv(details_path, index=False)
    mismatches = details[~details["all_checks_pass"]]
    mismatches.to_csv(mismatch_path, index=False)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "silver_root": SILVER_ROOT,
        "gold_path": GOLD_PATH,
        "silver_parquet_files": len(silver_paths),
        "silver_rows": int(len(silver)),
        "gold_rows": int(len(gold)),
        "matched_event_ids": int(len(joined)),
        "unmatched_silver_ids": int(len(silver) - len(joined)),
        "sample_size_requested": args.sample_size,
        "sample_size_tested": int(len(details)),
        "api_base_url": args.base_url,
        "expected_api_model_run_id": expected_run_id,
        "api_model_info": model_info,
        "gold_model_versions": sorted(gold["model_version"].dropna().unique().tolist()),
        "gold_thresholds": sorted(
            float(value) for value in gold["model_threshold"].dropna().unique()
        ),
        "probability_tolerance": args.tolerance,
        "checks": {
            column: int(details[column].sum()) for column in check_columns
        },
        "request_errors": int(details["error"].ne("").sum()),
        "mismatch_rows": int(len(mismatches)),
        "overall_pass": bool(details["all_checks_pass"].all()),
        "note": (
            "Gold does not contain model_run_id. The API run ID is checked "
            "against EXPECTED_MODEL_RUN_ID, but the exact Gold training run "
            "cannot be proven from Gold model_version alone."
        ),
        "details_file": str(details_path),
        "mismatches_file": str(mismatch_path),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== PARITY SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print(f"\nDetails:   {details_path}")
    print(f"Mismatches: {mismatch_path}")
    print(f"Summary:   {summary_path}")

    if not summary["overall_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
