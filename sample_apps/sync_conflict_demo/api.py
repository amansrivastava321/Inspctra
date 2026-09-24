from fastapi import FastAPI

app = FastAPI()


@app.get("/sync/jobs")
def list_sync_jobs():
    # Missing auth by design.
    return [{"id": "sync-1", "status": "running"}]
