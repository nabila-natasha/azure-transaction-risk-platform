import json
import os
from datetime import datetime, timezone

from azure.eventhub import EventHubConsumerClient
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient


EVENT_HUB_CONNECTION_STRING = os.environ["EVENT_HUB_CONNECTION_STRING"]
EVENT_HUB_NAME = os.environ["EVENT_HUB_NAME"]

STORAGE_ACCOUNT = "sttransactionbello"
FILESYSTEM = "synapse"
OUTPUT_DIR = "bronze/transactions/streaming"

credential = DefaultAzureCredential()

storage = DataLakeServiceClient(
    account_url=f"https://{STORAGE_ACCOUNT}.dfs.core.windows.net",
    credential=credential,
)

file_system = storage.get_file_system_client(FILESYSTEM)

consumer = EventHubConsumerClient.from_connection_string(
    conn_str=EVENT_HUB_CONNECTION_STRING,
    consumer_group="$Default",
    eventhub_name=EVENT_HUB_NAME,
)


def on_event_batch(partition_context, events):
    if not events:
        return

    lines = []

    for event in events:
        try:
            payload = json.loads(event.body_as_str())
            lines.append(json.dumps(payload))
        except json.JSONDecodeError:
            continue

    if not lines:
        return

    partition_id = partition_context.partition_id
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")

    path = (
        f"{OUTPUT_DIR}/"
        f"partition={partition_id}/"
        f"events_{timestamp}.jsonl"
    )

    data = ("\n".join(lines) + "\n").encode("utf-8")

    file_client = file_system.get_file_client(path)
    file_client.upload_data(data, overwrite=True)

    print(
        f"Partition {partition_id}: "
        f"wrote {len(lines)} events → {path}"
    )


print("Starting Event Hubs consumer...")

try:
    with consumer:
        consumer.receive_batch(
            on_event_batch=on_event_batch,
            starting_position="-1",
            max_wait_time=5,
        )
except KeyboardInterrupt:
    print("\nConsumer stopped.")
