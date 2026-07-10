import time
import os
import fitz  # PyMuPDF
from sqlalchemy import create_engine, Column, Integer, String, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
import enum

# Konfiguracja bazy danych
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://szczytnik_user:user_secure_password@db/szczytnik_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class JobStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer)
    status = Column(Enum(JobStatus))

class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    file_path = Column(String(500))

def process_pdf(job, issue):
    print(f"\nRozpoczynam analizę pliku: {issue.file_path}", flush=True)
    try:
        doc = fitz.open(issue.file_path)
        
        print("Skanowanie pierwszych 10 stron w poszukiwaniu potencjalnych tytułów...", flush=True)
        pages_to_scan = min(10, doc.page_count)
        
        for page_num in range(pages_to_scan):
            page = doc.load_page(page_num)
            # Pobieramy strukturę tekstu w formie słownika (dict)
            blocks = page.get_text("dict")["blocks"]
            
            for b in blocks:
                if "lines" in b:
                    for l in b["lines"]:
                        for s in l["spans"]:
                            font_size = s["size"]
                            text = s["text"].strip()
                            
                            # Filtrujemy pusty tekst i szukamy czcionek większych niż standardowy tekst (zakładamy > 12)
                            if font_size > 12 and len(text) > 4:
                                print(f"Strona {page_num + 1} | Rozmiar: {font_size:.1f} | Tekst: {text}", flush=True)
        
        doc.close()
        return True
    except Exception as e:
        print(f"Błąd podczas przetwarzania PDF: {e}", flush=True)
        return False

def main():
    print("Worker Szczytnik (Wersja Heurystyczna) uruchomiony...", flush=True)
    while True:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.status == JobStatus.PENDING).first()
            if job:
                print(f"\n--- Znaleziono nowe zadanie ID: {job.id} ---", flush=True)
                job.status = JobStatus.PROCESSING
                db.commit()
                
                issue = db.query(Issue).filter(Issue.id == job.issue_id).first()
                success = process_pdf(job, issue)
                
                job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
                db.commit()
                print(f"Zadanie ID: {job.id} zakończone.", flush=True)
        except Exception as e:
            print(f"Błąd zapytania do bazy danych: {e}", flush=True)
        finally:
            db.close()
        
        time.sleep(10)

if __name__ == "__main__":
    main()