#!/bin/bash
# Google Cloud Resource Provisioning and Deployment Script (Bash)
# This script provisions all pipeline resources and deploys the Flask application to Cloud Run.

set -eo pipefail

# --- 1. CONFIGURATION CONFIG ---
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "Error: No active Google Cloud project set. Run 'gcloud config set project <PROJECT_ID>' first."
    exit 1
fi

REGION="us-central1"
BUCKET_NAME="$PROJECT_ID-document-ingestion"
TOPIC_NAME="document-uploads-topic"
SUB_NAME="document-uploads-sub"
DATASET_NAME="document_pipeline"
TABLE_NAME="processed_metadata"
SERVICE_NAME="document-processor"

echo "========================================================="
echo "Deploying Document Processing Pipeline to GCP (Bash)"
echo "Project ID : $PROJECT_ID"
echo "Region     : $REGION"
echo "GCS Bucket : gs://$BUCKET_NAME"
echo "Pub/Sub    : Topic [$TOPIC_NAME] -> Sub [$SUB_NAME]"
echo "BigQuery   : Dataset [$DATASET_NAME] -> Table [$TABLE_NAME]"
echo "Cloud Run  : Service [$SERVICE_NAME]"
echo "========================================================="

# --- 2. ENABLE REQUIRED SERVICES ---
echo "[1/8] Enabling required GCP APIs..."
gcloud services enable storage.googleapis.com \
                       pubsub.googleapis.com \
                       run.googleapis.com \
                       bigquery.googleapis.com \
                       artifactregistry.googleapis.com \
                       cloudbuild.googleapis.com

# --- 3. CREATE STORAGE BUCKET ---
echo "[2/8] Setting up Cloud Storage Bucket..."
if gcloud storage buckets describe "gs://$BUCKET_NAME" &>/dev/null; then
    echo "Bucket gs://$BUCKET_NAME already exists."
else
    echo "Creating bucket gs://$BUCKET_NAME..."
    gcloud storage buckets create "gs://$BUCKET_NAME" --location="$REGION"
fi

# --- 4. CREATE PUB/SUB TOPIC ---
echo "[3/8] Setting up Pub/Sub Topic..."
if gcloud pubsub topics describe "$TOPIC_NAME" &>/dev/null; then
    echo "Pub/Sub Topic $TOPIC_NAME already exists."
else
    echo "Creating Pub/Sub Topic $TOPIC_NAME..."
    gcloud pubsub topics create "$TOPIC_NAME"
fi

# --- 5. GRANT PUBLISH PERMISSIONS TO STORAGE SERVICE ACCOUNT ---
echo "[4/8] Configuring IAM Permissions for Cloud Storage to Pub/Sub..."
GCS_SERVICE_ACCOUNT=$(gcloud storage service-agent)
echo "GCS Service Agent: $GCS_SERVICE_ACCOUNT"
echo "Granting Pub/Sub Publisher role to Cloud Storage service account on $TOPIC_NAME..."
gcloud pubsub topics add-iam-policy-binding "$TOPIC_NAME" \
    --member="serviceAccount:$GCS_SERVICE_ACCOUNT" \
    --role="roles/pubsub.publisher" >/dev/null

# Configure GCS notifications if they don't already exist
NOTIFICATIONS=$(gcloud storage buckets notifications list "gs://$BUCKET_NAME" --format="value(name)" 2>/dev/null || true)
if [ -z "$NOTIFICATIONS" ]; then
    echo "Creating Cloud Storage notification linking to Pub/Sub topic..."
    gcloud storage buckets notifications create "gs://$BUCKET_NAME" --topic="$TOPIC_NAME"
else
    echo "Cloud Storage bucket notification already exists."
fi

# --- 6. SETUP BIGQUERY DATASET AND TABLE ---
echo "[5/8] Setting up BigQuery..."

# Create Dataset if not exists
if bq show --dataset "$PROJECT_ID:$DATASET_NAME" &>/dev/null; then
    echo "BigQuery dataset $DATASET_NAME already exists."
else
    echo "Creating BigQuery Dataset $DATASET_NAME..."
    bq mk --dataset --location="$REGION" "$PROJECT_ID:$DATASET_NAME"
fi

# Create Table if not exists
if bq show "$PROJECT_ID:$DATASET_NAME.$TABLE_NAME" &>/dev/null; then
    echo "BigQuery table $DATASET_NAME.$TABLE_NAME already exists."
else
    echo "Creating BigQuery Table $DATASET_NAME.$TABLE_NAME with schema..."
    bq mk --table --description="Document metadata extracted by pipeline" \
          "$PROJECT_ID:$DATASET_NAME.$TABLE_NAME" ./scripts/schema.json
fi

# --- 7. DEPLOY CLOUD RUN SERVICE ---
echo "[6/8] Building container and deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region="$REGION" \
    --allow-unauthenticated \
    --set-env-vars="BQ_DATASET=$DATASET_NAME,BQ_TABLE=$TABLE_NAME,MOCK_GCP=false"

# Retrieve Cloud Run Service URL
RUN_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
echo "Cloud Run Service URL: $RUN_URL"

# --- 8. CREATE PUB/SUB PUSH SUBSCRIPTION ---
echo "[7/8] Setting up Pub/Sub Push Subscription..."
if gcloud pubsub subscriptions describe "$SUB_NAME" &>/dev/null; then
    echo "Updating Pub/Sub subscription $SUB_NAME endpoint to $RUN_URL/pubsub..."
    gcloud pubsub subscriptions update "$SUB_NAME" \
        --push-endpoint="$RUN_URL/pubsub"
else
    echo "Creating Pub/Sub subscription $SUB_NAME targeting Cloud Run endpoint..."
    gcloud pubsub subscriptions create "$SUB_NAME" \
        --topic="$TOPIC_NAME" \
        --push-endpoint="$RUN_URL/pubsub"
fi

# --- 9. SUMMARY ---
echo "========================================================="
echo "Deployment Completed Successfully!"
echo "1. Upload files to: gs://$BUCKET_NAME"
echo "2. Deployed Cloud Run Service: $RUN_URL"
echo "3. Query metadata in BigQuery: SELECT * FROM \`$PROJECT_ID.$DATASET_NAME.$TABLE_NAME\`"
echo "========================================================="
