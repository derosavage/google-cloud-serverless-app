import os
import json
import base64
import logging
from flask import Flask, request, jsonify, render_template
from google.cloud import storage
from google.cloud import bigquery
from src.ocr import process_document

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize Flask with template folder inside src/
app = Flask(__name__, template_folder="templates")

# Load configurations from environment variables
MOCK_GCP = os.environ.get("MOCK_GCP", "false").lower() == "true"
BQ_DATASET = os.environ.get("BQ_DATASET", "document_pipeline")
BQ_TABLE = os.environ.get("BQ_TABLE", "processed_metadata")

# In-memory database for local/mock mode simulation
MOCK_DOCUMENTS = [
    {
        "filename": "annual_financial_report.txt",
        "bucket": "my-mock-bucket",
        "size": 5241,
        "content_type": "text/plain",
        "word_count": 482,
        "tags": ["financial", "report", "text-format"],
        "ocr_text_preview": "DocuFlow Systems Annual Financial Review for Fiscal Year 2026. This confidential document outlines quarterly metrics and project investments.",
        "process_timestamp": "2026-06-23T11:45:00.000Z"
    },
    {
        "filename": "scanned_receipt_103.png",
        "bucket": "my-mock-bucket",
        "size": 240582,
        "content_type": "image/png",
        "word_count": 142,
        "tags": ["mock-ocr", "png-format", "receipt", "general"],
        "ocr_text_preview": "[Simulated OCR Preview for non-text file 'scanned_receipt_103.png']. Extracted 142 mock words including: invoice, total, due, payment.",
        "process_timestamp": "2026-06-23T11:20:00.000Z"
    }
]

# Initialize GCP Clients only if not in MOCK_GCP mode
storage_client = None
bq_client = None

if not MOCK_GCP:
    try:
        storage_client = storage.Client()
        bq_client = bigquery.Client()
        logger.info("GCP clients initialized successfully.")
    except Exception as e:
        logger.warning(f"Failed to initialize real GCP clients ({e}). Falling back to MOCK_GCP mode.")
        MOCK_GCP = True
else:
    logger.info("Running in MOCK_GCP mode. GCS downloads and BigQuery uploads will be simulated.")

@app.route("/", methods=["GET"])
def index():
    """Renders the HTML Dashboard monitoring page."""
    return render_template("dashboard.html")

@app.route("/api/documents", methods=["GET"])
def get_documents():
    """
    Fetches the processed documents metadata from BigQuery or
    returns mock data if MOCK_GCP mode is active.
    """
    if MOCK_GCP:
        # Return local in-memory records
        return jsonify({
            "documents": MOCK_DOCUMENTS,
            "mock_gcp": True
        }), 200

    try:
        project_id = bq_client.project
        table_ref = f"{project_id}.{BQ_DATASET}.{BQ_TABLE}"
        
        # Query BigQuery sorting by processed timestamp descending
        query = f"""
            SELECT filename, bucket, size, content_type, word_count, tags, ocr_text_preview, process_timestamp
            FROM `{table_ref}`
            ORDER BY process_timestamp DESC
            LIMIT 100
        """
        query_job = bq_client.query(query)
        rows = query_job.result()
        
        docs = []
        for row in rows:
            docs.append({
                "filename": row.filename,
                "bucket": row.bucket,
                "size": row.size,
                "content_type": row.content_type,
                "word_count": row.word_count,
                # REPEATED STRING is returned as list of strings or None
                "tags": list(row.tags) if row.tags else [],
                "ocr_text_preview": row.ocr_text_preview,
                "process_timestamp": row.process_timestamp.isoformat() if hasattr(row.process_timestamp, 'isoformat') else str(row.process_timestamp)
            })
            
        return jsonify({
            "documents": docs,
            "mock_gcp": False
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to query BigQuery: {e}. Falling back to mock data.")
        # Fallback to mock data and display error message in logs/metadata
        return jsonify({
            "documents": MOCK_DOCUMENTS,
            "mock_gcp": True,
            "error": str(e)
        }), 200

@app.route("/pubsub", methods=["POST"])
def pubsub_push_handler():
    """
    Handles Pub/Sub push messages triggered by GCS upload notifications.
    """
    envelope = request.get_json()
    if not envelope:
        logger.error("No JSON payload received.")
        return "Bad Request: No JSON payload", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        logger.error("Invalid Pub/Sub message format.")
        return "Bad Request: Invalid Pub/Sub message format", 400

    pubsub_message = envelope["message"]
    attributes = pubsub_message.get("attributes", {})
    
    # Filter event type
    event_type = attributes.get("eventType")
    if event_type and event_type != "OBJECT_FINALIZE":
        logger.info(f"Skipping non-finalize event: {event_type}")
        return f"Event {event_type} ignored", 200

    # Decode payload
    if "data" not in pubsub_message:
        logger.error("Pub/Sub message missing data field.")
        return "Bad Request: Missing data field", 400

    try:
        data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        gcs_event = json.loads(data_str)
    except Exception as e:
        logger.error(f"Failed to decode message data: {e}")
        return "Bad Request: Invalid base64 or JSON in data", 400

    bucket_name = gcs_event.get("bucket")
    file_name = gcs_event.get("name")
    file_size = int(gcs_event.get("size", 0))
    content_type = gcs_event.get("contentType", "application/octet-stream")

    if not bucket_name or not file_name:
        logger.error(f"Missing bucket or name in GCS event.")
        return "Bad Request: Missing bucket or name", 400

    logger.info(f"Processing file: gs://{bucket_name}/{file_name} (Size: {file_size} bytes, Content-Type: {content_type})")

    # Download GCS content
    file_content = b""
    
    # Check if a custom file content header was provided by our dashboard simulator
    mock_content_header = request.headers.get("X-Mock-File-Content")
    
    if mock_content_header:
        try:
            file_content = base64.b64decode(mock_content_header)
            logger.info("Using simulated content from request header.")
        except Exception as e:
            logger.warning(f"Failed to decode custom mock file content header: {e}")
            file_content = b"Simulated contents"
    elif MOCK_GCP:
        logger.info(f"[MOCK] Simulating file download for gs://{bucket_name}/{file_name}")
        if file_name.lower().endswith(".txt"):
            file_content = (
                b"INVOICE #1024\n"
                b"Date: 2026-06-23\n"
                b"Total Due: $450.00\n"
                b"Please process this financial report and payment receipt immediately. "
                b"This document is highly confidential and contains urgent meeting details."
            )
        else:
            file_content = b"\x00\x01\x02\x03\x04"
    else:
        try:
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(file_name)
            file_content = blob.download_as_bytes()
            logger.info(f"Successfully downloaded {len(file_content)} bytes from GCS.")
        except Exception as e:
            logger.error(f"Failed to download file from GCS: {e}")
            return f"Error downloading file: {str(e)}", 500

    # Perform Simulated OCR and Metadata Extraction
    try:
        metadata = process_document(bucket_name, file_name, file_size, content_type, file_content)
        logger.info(f"Extracted metadata: {json.dumps(metadata)}")
    except Exception as e:
        logger.error(f"Failed during OCR/Metadata extraction: {e}")
        return f"Error during OCR processing: {str(e)}", 500

    # Store Metadata
    if MOCK_GCP:
        logger.info(f"[MOCK] Appending processed row to in-memory metadata collection.")
        # Insert at the beginning so it shows up first in the UI
        MOCK_DOCUMENTS.insert(0, metadata)
    else:
        try:
            project_id = bq_client.project
            table_ref = f"{project_id}.{BQ_DATASET}.{BQ_TABLE}"
            errors = bq_client.insert_rows_json(table_ref, [metadata])
            
            if errors:
                logger.error(f"Failed to insert row into BigQuery: {errors}")
                return f"BigQuery Insert Errors: {str(errors)}", 500
            
            logger.info(f"Successfully inserted metadata row into BigQuery: {table_ref}")
        except Exception as e:
            logger.error(f"Exception during BigQuery insert: {e}")
            return f"BigQuery Exception: {str(e)}", 500

    return jsonify({"status": "success", "processed_file": file_name}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    if "MOCK_GCP" not in os.environ:
        os.environ["MOCK_GCP"] = "true"
        MOCK_GCP = True
        logger.info("MOCK_GCP not specified. Defaulting to true for local execution.")
    app.run(host="0.0.0.0", port=port)
