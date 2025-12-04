from google.cloud import logging_v2
import os

project_id = os.popen("gcloud config get-value project").read().strip()
client = logging_v2.Client(project=project_id)

# Query logs directly
filter_str = 'resource.labels.service_name="aiops-demo-service" AND severity>="WARNING"'
entries = list(client.list_entries(filter_=filter_str, max_results=5))

print(f"\nFound {len(entries)} entries\n")

for i, entry in enumerate(entries, 1):
    print(f"{i}. Severity: {entry.severity}")

    # Check what fields exist
    if hasattr(entry, 'text_payload') and entry.text_payload:
        print(f"   text_payload: {entry.text_payload[:100]}")

    if hasattr(entry, 'json_payload') and entry.json_payload:
        print(f"   json_payload: {str(entry.json_payload)[:100]}")

    if hasattr(entry, 'http_request') and entry.http_request:
        http = entry.http_request
        if isinstance(http, dict):
            status = http.get('status')
            method = http.get('requestMethod')
            print(f"   HTTP: {method} -> {status}")
        else:
            print(f"   HTTP: {http}")
    print()