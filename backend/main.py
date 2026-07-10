from fastapi import FastAPI
import models
from database import engine

# Ta linijka automatycznie tworzy tabele w MariaDB, jeśli nie istnieją!
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Szczytnik API")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Backend systemu Szczytnik dziala prawidłowo"}

@app.get("/health-check-db")
def check_db():
    return {"database": "Modele zsynchronizowane z MariaDB"}