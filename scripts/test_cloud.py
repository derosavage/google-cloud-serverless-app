import time
import os
import sys
from google.cloud import storage
from google.cloud import bigquery

def main():
    print("=========================================================")
    print("Running GCP Pipeline Cloud Integration Test")
    print("=========================================================")

    # Get active project ID from gcloud config or environment
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        try:
            import subprocess
            # Use shell=True to resolve batch scripts (gcloud.cmd) on Windows
            project_id = subprocess.check_output(
                ["gcloud", "config", "get-value", "project"],
                text=True,
                shell=True
            ).strip()
        except Exception:
            pass

    if not project_id:
        print("Error: Could not determine Google Cloud Project ID.")
        print("Please set the GOOGLE_CLOUD_PROJECT environment variable or authenticate with gcloud.")
        sys.exit(1)

    bucket_name = f"{project_id}-document-ingestion"
    dataset_name = "document_pipeline"
    table_name = "processed_metadata"
    test_filename = f"cloud_test_invoice_{int(time.time())}.txt"

    print(f"Project ID : {project_id}")
    print(f"GCS Bucket : gs://{bucket_name}")
    print(f"BQ Table   : {project_id}.{dataset_name}.{table_name}")
    print(f"Test File  : {test_filename}")
    print("=========================================================")

    # 1. Initialize Clients
    try:
        storage_client = storage.Client(project=project_id)
        bq_client = bigquery.Client(project=project_id)
    except Exception as e:
        print(f"Error initializing GCP Clients: {e}")
        print("Please run 'gcloud auth application-default login' to set up local credentials.")
        sys.exit(1)

    # 2. Upload file to GCS
    try:
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(test_filename)
        
        test_content = (
            "INVOICE FOR CLOUD PIPELINE TESTING\n"
            "Invoice Number: INV-2026-999\n"
            "Date: 2026-06-23\n"
            "This report details the cloud-based serverless configuration. "
            "Please process this financial resume. We need an agreement and contract signed soon. "
            "Mark this document as highly confidential and urgent."
        )
        
        print(f"Uploading file '{test_filename}' to GCS bucket '{bucket_name}'...")
        blob.upload_from_string(test_content, content_type="text/plain")
        print("File uploaded successfully!")
    except Exception as e:
        print(f"Failed to upload test file to GCS: {e}")
        sys.exit(1)

    # 3. Wait for event processing
    wait_seconds = 8
    print(f"Sleeping for {wait_seconds} seconds to let Pub/Sub trigger Cloud Run and write to BigQuery...")
    for i in range(wait_seconds, 0, -1):
        print(f"{i}...", end="", flush=True)
        time.sleep(1)
    print()

    # 4. Query BigQuery table to verify insertion
    try:
        query = f"""
            SELECT filename, bucket, size, content_type, word_count, tags, ocr_text_preview, process_timestamp
            FROM `{project_id}.{dataset_name}.{table_name}`
            WHERE filename = @filename
            LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("filename", "STRING", test_filename)
            ]
        )
        
        print("Querying BigQuery table for the processed metadata...")
        query_job = bq_client.query(query, job_config=job_config)
        results = list(query_job.result())

        if len(results) == 0:
            print("❌ FAILED: No record found in BigQuery table.")
            print("Possible issues:")
            print("1. Cloud Run service had an error (check Cloud Run logs).")
            print("2. Pub/Sub push subscription failed (check Pub/Sub logs/metrics).")
            print("3. BigQuery streaming write failed.")
            sys.exit(1)
        
        # Display the result
        row = results[0]
        print("✅ SUCCESS: Record found in BigQuery!")
        print("---------------------------------------------------------")
        print(f"Filename       : {row.filename}")
        print(f"Bucket         : {row.bucket}")
        print(f"Size (Bytes)   : {row.size}")
        print(f"Content Type   : {row.content_type}")
        print(f"Word Count     : {row.word_count}")
        print(f"Tags           : {row.tags}")
        print(f"OCR Preview    : {row.ocr_text_preview}")
        print(f"Processed At   : {row.process_timestamp}")
        print("---------------------------------------------------------")

    except Exception as e:
        print(f"Error querying BigQuery: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
