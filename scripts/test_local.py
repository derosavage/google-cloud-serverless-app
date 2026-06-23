import json
import base64
import urllib.request
import urllib.error
import sys

LOCAL_URL = "http://localhost:8080/pubsub"

def make_pubsub_payload(bucket: str, filename: str, size: int, content_type: str, event_type: str = "OBJECT_FINALIZE") -> dict:
    """Helper to generate a Pub/Sub push notification payload mimicking GCS."""
    gcs_notification = {
        "kind": "storage#object",
        "bucket": bucket,
        "name": filename,
        "size": str(size),
        "contentType": content_type
    }
    
    # Base64 encode the GCS notification data
    json_bytes = json.dumps(gcs_notification).encode("utf-8")
    b64_data = base64.b64encode(json_bytes).decode("utf-8")
    
    return {
        "message": {
            "attributes": {
                "eventType": event_type,
                "bucketId": bucket,
                "objectId": filename
            },
            "data": b64_data,
            "messageId": "9999999999",
            "publishTime": "2026-06-23T12:00:00.000Z"
        },
        "subscription": "projects/mock-project/subscriptions/mock-sub"
    }

def send_test_request(name: str, payload: dict):
    print(f"\n--- Running Test: {name} ---")
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        LOCAL_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
            print(f"Status Code: {status_code}")
            print(f"Response Body: {response_body}")
            if status_code == 200:
                print(f"Result: SUCCESS")
            else:
                print(f"Result: FAILED (Unexpected status code)")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        print(f"Response: {e.read().decode('utf-8')}")
        print("Result: FAILED")
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}")
        print(f"Is the local Flask server running at {LOCAL_URL}?")
        print("Result: FAILED")
        sys.exit(1)

def main():
    print("Starting local integration tests...")
    
    # Test Case 1: Plain Text file upload (should count words and parse tags)
    payload_text = make_pubsub_payload(
        bucket="my-local-ingestion-bucket",
        filename="invoice_contract.txt",
        size=1024,
        content_type="text/plain"
    )
    send_test_request("Text File (.txt) processing", payload_text)
    
    # Test Case 2: Binary Image file upload (should simulate mock OCR)
    payload_image = make_pubsub_payload(
        bucket="my-local-ingestion-bucket",
        filename="scanned_receipt.png",
        size=450213,
        content_type="image/png"
    )
    send_test_request("Binary File (.png) processing", payload_image)

    # Test Case 3: Ignored Event Type (e.g. OBJECT_DELETE)
    payload_delete = make_pubsub_payload(
        bucket="my-local-ingestion-bucket",
        filename="deleted_doc.txt",
        size=0,
        content_type="text/plain",
        event_type="OBJECT_DELETE"
    )
    send_test_request("Ignored Event Type (OBJECT_DELETE)", payload_delete)

if __name__ == "__main__":
    main()
