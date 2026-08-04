from fastapi import FastAPI

app = FastAPI(title="ATS Diagnostic API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
