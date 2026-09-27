import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone

from azure.eventhub import EventData, EventHubProducerClient


CONNECTION_STRING = os.environ["EVENT_HUB_CONNECTION_STRING"]
EVENT_HUB_NAME = os.environ["EVENT_HUB_NAME"]

INPUT_FILE = os.getenv(
    "STREAM_INPUT_FILE",
    "data/raw/split/transactions_streaming.csv",
)

MAX_EVENTS_PER_BATCH = int(
    os.getenv("EVENT_BATCH_SIZE", "20")
)

PACE_SECONDS = float(
    os.getenv("EVENT_PACE_SECONDS", "0.2")
)

MAX_RETRIES = 6
INITIAL_RETRY_DELAY = 2


def make_event_id(row):
    """Create a deterministic identifier for a transaction."""
    stable_value = "|".join(
        [
            row["trans_date_trans_time"],
            row["cc_num"],
            row["amt"],
            row["merchant"],
        ]
    )

    return hashlib.sha256(
        stable_value.encode("utf-8")
    ).hexdigest()


def send_batch_with_retry(producer, batch):
    """Send a batch with exponential backoff for transient failures."""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            producer.send_batch(batch)
            return

        except Exception as exc:
            if attempt == MAX_RETRIES:
                raise

            delay = INITIAL_RETRY_DELAY * (2 ** (attempt - 1))

            print(
                f"Send failed "
                f"(attempt {attempt}/{MAX_RETRIES}). "
                f"Retrying in {delay}s: {exc}"
            )

            time.sleep(delay)


producer = EventHubProducerClient.from_connection_string(
    conn_str=CONNECTION_STRING,
    eventhub_name=EVENT_HUB_NAME,
)

sent = 0

with producer:
    with open(
        INPUT_FILE,
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        batch = producer.create_batch()
        batch_count = 0

        for row in reader:

            payload = {
                "event_id": make_event_id(row),
                "event_time": row["trans_date_trans_time"],
                "ingestion_time": datetime.now(
                    timezone.utc
                ).isoformat(),
                "source": "sparkov_simulated_transactions",
                "payload": row,
            }

            event = EventData(
                json.dumps(payload)
            )

            try:
                batch.add(event)
                batch_count += 1

            except ValueError:
                send_batch_with_retry(
                    producer,
                    batch,
                )

                sent += batch_count

                print(
                    f"Sent {sent:,} events"
                )

                time.sleep(PACE_SECONDS)

                batch = producer.create_batch()
                batch.add(event)
                batch_count = 1

            if batch_count >= MAX_EVENTS_PER_BATCH:

                send_batch_with_retry(
                    producer,
                    batch,
                )

                sent += batch_count

                print(
                    f"Sent {sent:,} events"
                )

                time.sleep(PACE_SECONDS)

                batch = producer.create_batch()
                batch_count = 0

        if batch_count > 0:

            send_batch_with_retry(
                producer,
                batch,
            )

            sent += batch_count

print(
    f"Streaming replay completed: "
    f"{sent:,} events sent."
)

