from fastapi import FastAPI

app = FastAPI(title="CoachOS Athlete Service")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "athlete"}
