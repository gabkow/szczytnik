from fastapi import FastAPI

app = FastAPI(title="Szczytnik API")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Backend systemu Szczytnik dziala prawidłowo"}

@app.get("/health-check-db")
def check_db():
    return {"database": "connected_mock"}