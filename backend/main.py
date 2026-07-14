from fastapi import FastAPI, Depends, HTTPException, APIRouter, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import models
from database import engine, SessionLocal

# Automatyczne tworzenie tabel przy starcie (jeśli jeszcze nie istnieją)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Szczytnik API")

# Służy do bezpiecznego otwierania i zamykania sesji bazy danych przy każdym zapytaniu
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Model Pydantic - definiuje jakich danych (i w jakim formacie) oczekujemy w zapytaniu POST
class IssueCreate(BaseModel):
    title: str
    issue_number: str
    file_path: str

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Backend systemu Szczytnik działa prawidłowo"}

# Nowy endpoint do wprowadzania czasopisma
@app.post("/issues/", status_code=status.HTTP_201_CREATED)
def create_issue(issue_data: IssueCreate, db: Session = Depends(get_db)):
    
    # 1. Sprawdzenie, czy dany numer czasopisma był już przetwarzany (ochrona przed duplikatami)
    existing_issue = db.query(models.Issue).filter(
        models.Issue.title == issue_data.title,
        models.Issue.issue_number == issue_data.issue_number
    ).first()
    
    if existing_issue:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="To czasopismo o podanym numerze zostało już wprowadzone do systemu."
        )
    
    # 2. Zapis nowego czasopisma do bazy danych
    new_issue = models.Issue(
        title=issue_data.title,
        issue_number=issue_data.issue_number,
        file_path=issue_data.file_path
    )
    db.add(new_issue)
    db.commit()
    db.refresh(new_issue) # Pobiera z bazy nadane automatycznie ID
    
    # 3. Automatyczne utworzenie zadania kolejki (Job) dla Workera
    new_job = models.Job(
        issue_id=new_issue.id,
        status=models.JobStatus.PENDING
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    return {
        "status": "success",
        "message": "Czasopismo zostało zarejestrowane. Zadanie dodano do kolejki przetwarzania.",
        "data": {
            "issue_id": new_issue.id,
            "job_id": new_job.id,
            "status": new_job.status.value
        }
    }

# Edpoint debug do wyświetlania zawartości bazy
@app.get("/api/debug/database-view")
def get_database_debug_view(db: Session = Depends(get_db)):
    try:
        # 1. Pobieramy wszystkie numery czasopism (issues)
        issues = db.query(Issue).all()
        result = []
        
        for issue in issues:
            # 2. Dla każdego numeru pobieramy pierwsze 3 artykuły posortowane wg strony startowej
            articles = (
                db.query(Article)
                .filter(Article.issue_id == issue.id)
                .order_by(Article.start_page.asc())
                .limit(3)
                .all()
            )
            
            for art in articles:
                result.append({
                    "issue_title": issue.title,
                    "issue_number": issue.issue_number,
                    "article_title": art.title,
                    "author": art.author,
                    "start_page": art.start_page,
                    "keywords": art.keywords,
                    "abstract": art.abstract
                })
                
        return result
    except Exception as e:
        return {"error": f"Błąd pobierania danych: {str(e)}"}
    