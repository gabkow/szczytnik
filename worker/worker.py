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

# Minimalne modele bazy danych potrzebne Workerowi
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
    print(f"Rozpoczynam przetwarzanie pliku: {issue.file_path}", flush=True)
    try:
        # Otwieramy plik PDF za pomocą PyMuPDF
        doc = fitz.open(issue.file_path)
        print(f"Dokument otwarty pomyślnie. Liczba stron: {doc.page_count}", flush=True)
        
        # Próbujemy wyciągnąć spis treści (tzw. outlines/bookmarks)
        toc = doc.get_toc()
        if toc:
            print("SUKCES: Znaleziono natywny spis treści! Oto on:", flush=True)
            for item in toc:
                # Format: [poziom_zagnieżdżenia, tytuł, numer_strony]
                print(f" - Poziom {item[0]}: {item[1]} (Strona {item[2]})", flush=True)
        else:
            print("INFORMACJA: Brak natywnego spisu treści. Będziemy musieli analizować tekst lub wyrażenia regularne.", flush=True)
        
        doc.close()
        return True
    except Exception as e:
        print(f"Błąd podczas przetwarzania PDF: {e}", flush=True)
        return False

def main():
    print("Worker Szczytnik uruchomiony. Czekam na zadania...", flush=True)
    while True:
        db = SessionLocal()
        try:
            # Szukamy pierwszego zadania ze statusem PENDING
            job = db.query(Job).filter(Job.status == JobStatus.PENDING).first()
            if job:
                print(f"\n--- Znaleziono nowe zadanie ID: {job.id} ---", flush=True)
                
                # Oznaczamy jako przetwarzane
                job.status = JobStatus.PROCESSING
                db.commit()
                
                # Pobieramy dane o czasopiśmie
                issue = db.query(Issue).filter(Issue.id == job.issue_id).first()
                
                # Przetwarzamy plik
                success = process_pdf(job, issue)
                
                # Aktualizujemy status na końcowy
                job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
                db.commit()
                print(f"Zadanie ID: {job.id} zakończone statusem: {job.status.value}", flush=True)
        except Exception as e:
            print(f"Błąd zapytania do bazy danych: {e}", flush=True)
        finally:
            db.close()
        
        # Czekamy 10 sekund przed kolejnym sprawdzeniem bazy
        time.sleep(10)

if __name__ == "__main__":
    main()
