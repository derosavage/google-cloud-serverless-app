# Google Cloud Resource Provisioning and Deployment Script (PowerShell)
# This script provisions all pipeline resources and deploys the Flask application to Cloud Run.

# Set error action preference to continue so we can check $LASTEXITCODE manually
$ErrorActionPreference = "Continue"

# --- 1. CONFIGURATION CONFIG ---
# Get active GCP Project ID, or define it here
$PROJECT_ID_raw = (gcloud config get-value project)
if (-not $PROJECT_ID_raw -or $PROJECT_ID_raw -eq "(unset)") {
    Write-Error "No active Google Cloud project set. Please run 'gcloud config set project <PROJECT_ID>' first."
    exit 1
}
$PROJECT_ID = ($PROJECT_ID_raw -join "").Trim()

$REGION = "us-central1"
$BUCKET_NAME = "$PROJECT_ID-document-ingestion"
$TOPIC_NAME = "document-uploads-topic"
$SUB_NAME = "document-uploads-sub"
$DATASET_NAME = "document_pipeline"
$TABLE_NAME = "processed_metadata"
$SERVICE_NAME = "document-processor"

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "Deploying Document Processing Pipeline to GCP" -ForegroundColor Cyan
Write-Host "Project ID : $PROJECT_ID" -ForegroundColor Yellow
Write-Host "Region     : $REGION" -ForegroundColor Yellow
Write-Host "GCS Bucket : gs://$BUCKET_NAME" -ForegroundColor Yellow
Write-Host "Pub/Sub    : Topic [$TOPIC_NAME] -> Sub [$SUB_NAME]" -ForegroundColor Yellow
Write-Host "BigQuery   : Dataset [$DATASET_NAME] -> Table [$TABLE_NAME]" -ForegroundColor Yellow
Write-Host "Cloud Run  : Service [$SERVICE_NAME]" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Cyan

# --- 2. ENABLE REQUIRED SERVICES ---
Write-Host "[1/8] Enabling required GCP APIs..." -ForegroundColor Green
gcloud services enable storage.googleapis.com `
                       pubsub.googleapis.com `
                       run.googleapis.com `
                       bigquery.googleapis.com `
                       artifactregistry.googleapis.com `
                       cloudbuild.googleapis.com
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to enable required GCP APIs."
    exit 1
}

# --- 3. CREATE STORAGE BUCKET ---
Write-Host "[2/8] Setting up Cloud Storage Bucket..." -ForegroundColor Green
$null = gcloud storage buckets describe gs://$BUCKET_NAME --format="value(name)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating bucket gs://$BUCKET_NAME..."
    gcloud storage buckets create gs://$BUCKET_NAME --location=$REGION
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Cloud Storage bucket."
        exit 1
    }
} else {
    Write-Host "Bucket gs://$BUCKET_NAME already exists." -ForegroundColor Gray
}

# --- 4. CREATE PUB/SUB TOPIC ---
Write-Host "[3/8] Setting up Pub/Sub Topic..." -ForegroundColor Green
$null = gcloud pubsub topics describe $TOPIC_NAME --format="value(name)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Pub/Sub Topic $TOPIC_NAME..."
    gcloud pubsub topics create $TOPIC_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Pub/Sub topic."
        exit 1
    }
} else {
    Write-Host "Pub/Sub Topic $TOPIC_NAME already exists." -ForegroundColor Gray
}

# --- 5. GRANT PUBLISH PERMISSIONS TO STORAGE SERVICE ACCOUNT ---
Write-Host "[4/8] Configuring IAM Permissions for Cloud Storage to Pub/Sub..." -ForegroundColor Green
$gcs_service_account_raw = (gcloud storage service-agent)
if ($LASTEXITCODE -ne 0 -or -not $gcs_service_account_raw) {
    Write-Error "Failed to retrieve Cloud Storage service account."
    exit 1
}
$gcs_service_account = ($gcs_service_account_raw -join "").Trim()
Write-Host "GCS Service Agent: $gcs_service_account"

# Implement retry loop for IAM propagation delays
$success = $false
$retryCount = 0
$maxRetries = 6

while (-not $success -and $retryCount -lt $maxRetries) {
    Write-Host "Granting Pub/Sub Publisher role to Cloud Storage service account on $TOPIC_NAME..."
    gcloud pubsub topics add-iam-policy-binding $TOPIC_NAME `
        --member="serviceAccount:$gcs_service_account" `
        --role="roles/pubsub.publisher" > $null
    
    if ($LASTEXITCODE -eq 0) {
        $success = $true
        Write-Host "IAM permissions granted successfully!" -ForegroundColor Green
    } else {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "IAM propagation delay detected (Service account may not be fully active yet). Retrying in 5 seconds ($retryCount/$maxRetries)..." -ForegroundColor Yellow
            Start-Sleep -Seconds 5
        }
    }
}

if (-not $success) {
    Write-Error "Failed to grant Pub/Sub publisher permissions to Cloud Storage service account after multiple attempts."
    exit 1
}

# Configure GCS notifications if they don't already exist
$notifications = gcloud storage buckets notifications list gs://$BUCKET_NAME --format="value(name)" 2>$null
if ($LASTEXITCODE -ne 0 -or -not $notifications) {
    Write-Host "Creating Cloud Storage notification linking to Pub/Sub topic..."
    gcloud storage buckets notifications create gs://$BUCKET_NAME --topic=$TOPIC_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create Cloud Storage bucket notifications."
        exit 1
    }
} else {
    Write-Host "Cloud Storage bucket notification already exists." -ForegroundColor Gray
}

# --- 6. SETUP BIGQUERY DATASET AND TABLE ---
Write-Host "[5/8] Setting up BigQuery..." -ForegroundColor Green

# Create Dataset if not exists
$null = bq show --dataset "${PROJECT_ID}:${DATASET_NAME}" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating BigQuery Dataset $DATASET_NAME..."
    bq mk --dataset --location=$REGION "${PROJECT_ID}:${DATASET_NAME}"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create BigQuery Dataset."
        exit 1
    }
} else {
    Write-Host "BigQuery dataset $DATASET_NAME already exists." -ForegroundColor Gray
}

# Create Table if not exists
$null = bq show "${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating BigQuery Table $DATASET_NAME.$TABLE_NAME with schema..."
    bq mk --table --description="Document metadata extracted by pipeline" `
          "${PROJECT_ID}:${DATASET_NAME}.${TABLE_NAME}" .\scripts\schema.json
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create BigQuery Table."
        exit 1
    }
} else {
    Write-Host "BigQuery table $DATASET_NAME.$TABLE_NAME already exists." -ForegroundColor Gray
}

# --- 7. DEPLOY CLOUD RUN SERVICE ---
Write-Host "[6/8] Building container and deploying to Cloud Run..." -ForegroundColor Green
gcloud run deploy $SERVICE_NAME `
    --source . `
    --region=$REGION `
    --allow-unauthenticated `
    --set-env-vars="BQ_DATASET=$DATASET_NAME,BQ_TABLE=$TABLE_NAME,MOCK_GCP=false" `
    --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to deploy Cloud Run service."
    exit 1
}

# Retrieve Cloud Run Service URL
$RUN_URL_raw = (gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
$RUN_URL = ($RUN_URL_raw -join "").Trim()
Write-Host "Cloud Run Service URL: $RUN_URL" -ForegroundColor Yellow

# --- 8. CREATE PUB/SUB PUSH SUBSCRIPTION ---
Write-Host "[7/8] Setting up Pub/Sub Push Subscription..." -ForegroundColor Green
$null = gcloud pubsub subscriptions describe $SUB_NAME --format="value(name)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Pub/Sub subscription $SUB_NAME targeting Cloud Run endpoint..."
    gcloud pubsub subscriptions create $SUB_NAME `
        --topic=$TOPIC_NAME `
        --push-endpoint="$RUN_URL/pubsub"
} else {
    Write-Host "Updating Pub/Sub subscription $SUB_NAME endpoint to $RUN_URL/pubsub..."
    gcloud pubsub subscriptions update $SUB_NAME `
        --push-endpoint="$RUN_URL/pubsub"
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to set up Pub/Sub subscription."
    exit 1
}

# --- 9. SUMMARY ---
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "Deployment Completed Successfully!" -ForegroundColor Green
Write-Host "1. Upload files to: gs://$BUCKET_NAME" -ForegroundColor Yellow
Write-Host "2. Deployed Cloud Run Service: $RUN_URL" -ForegroundColor Yellow
Write-Host "3. Query metadata in BigQuery: SELECT * FROM ``${PROJECT_ID}.${DATASET_NAME}.${TABLE_NAME}``" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Cyan
