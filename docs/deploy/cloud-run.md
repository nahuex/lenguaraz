# Cloud Run — managed deployment on Google Cloud

Cloud Run runs the same container without a VM. Two things make Lenguaraz different from a
stateless web app, and the flags below exist because of them (lessons from Google's own
broadcast-translation reference deployment, see `.specify/memory/prior-art.md`, L6):

1. **Stages are in-process state** (one transcription session and one ffmpeg per stage).
   Run **exactly one instance** (`--min-instances=1 --max-instances=1`) so every viewer and
   the operator see the same stages. Horizontal scale is done with more services, each
   owning a subset of `stages.yaml` (`docs/deploy/scaling.md`).
2. **Long-lived connections.** WebSockets from the audience and the outbound Live API
   session both need the request timeout at its maximum and CPU always allocated.

## Deploy

```bash
PROJECT=my-gcp-project
REGION=us-central1

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# Secrets (never in the image, never in env files)
printf '%s' 'YOUR_GEMINI_API_KEY' | gcloud secrets create gemini-api-key --data-file=-
openssl rand -hex 32 | gcloud secrets create admin-token --data-file=-
gcloud secrets create stages-yaml --data-file=stages.yaml        # your event, mounted as a file

# Build and deploy from the repo root
gcloud run deploy lenguaraz \
  --source . --region "$REGION" --allow-unauthenticated \
  --port 8000 --cpu 2 --memory 2Gi \
  --min-instances 1 --max-instances 1 \
  --concurrency 250 --timeout 3600 --no-cpu-throttling --session-affinity \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest,ADMIN_TOKEN=admin-token:latest,/config/stages.yaml=stages-yaml:latest" \
  --set-env-vars "ENGINE=gemini,STAGES_FILE=/config/stages.yaml,HOST=0.0.0.0,PORT=8000"
```

`--timeout 3600` is the Cloud Run maximum for HTTP/WebSocket requests: audience browsers
reconnect automatically when the hour is up (the Fogón client backs off and resumes).
`--no-cpu-throttling` keeps the CPU allocated between requests, which the ffmpeg decoders
and the Live session need. `--session-affinity` keeps a browser on the same instance if you
ever run more than one.

Updating the stages file: `gcloud secrets versions add stages-yaml --data-file=stages.yaml`
and redeploy (or `gcloud run services update lenguaraz --region $REGION` with the same
`--set-secrets`).

## Audio in

Cloud Run accepts inbound **HTTP only**, so SRT/RTMP listeners do not work there. Use a
**pull** source: an HLS URL, an RTMP/SRT/RTSP stream your media server publishes, or a file
in a mounted bucket (`gcloud run services update … --add-volume name=media,type=cloud-storage,bucket=BUCKET --add-volume-mount volume=media,mount-path=/media`
then `source: /media/talk.mp4`). See `docs/deploy/audio-sources.md`.

## Checks

```bash
URL=$(gcloud run services describe lenguaraz --region "$REGION" --format 'value(status.url)')
curl -s "$URL/healthz"
open "$URL/fogon/main"
```

Cloud Run's filesystem is read-only except `/tmp`, the container runs as the non-root user
from the Dockerfile, and logs go to Cloud Logging as JSON (filter by `stage_id`).

## Cost notes

An always-on instance with 2 vCPU / 2 GiB and CPU always allocated is billed for the whole
event, plus egress for the caption WebSockets (text, negligible). Gemini usage is the same as
anywhere else (`docs/cost.md`). Delete the service after the event:
`gcloud run services delete lenguaraz --region "$REGION"`.
