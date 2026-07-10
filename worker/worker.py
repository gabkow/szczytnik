import time
import os
import fitz  # PyMuPDF
from sqlalchemy import create_engine, Column, Integer, String, Enum, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
import enum

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
    issue_number = Column(String(50))
    file_path = Column(String(500))

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("issues.id"))
    title = Column(String(500))
    author = Column(String(255))
    abstract = Column(Text)
    keywords = Column(String(255))
    start_page = Column(Integer)
    end_page = Column(Integer)
    file_path = Column(String(500))

def analyze_and_slice(issue_id, file_path, db):
    try:
        doc = fitz.open(file_path)
        detected_articles = []
        
        # Krok 1: Skanowanie stron w poszukiwaniu nagłówków (czcionka >= 22)
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            blocks = page.get_text("dict")["blocks"]
            
            page_titles = []
            for b in blocks:
                if "lines" in b:
                    for l in b["lines"]:
                        for s in l["spans"]:
                            if s["size"] >= 20.0:
                                text = s["text"].strip()
                                if len(text) > 3:
                                    page_titles.append(text)
            
            if page_titles:
                # Łączymy linie z tej samej strony w jeden tytuł
                full_title = " ".join(page_titles)
                
                # Unikamy duplikowania tego samego tytułu na jednej stronie
                if not detected_articles or detected_articles[-1]["start_page"] != page_num + 1:
                    detected_articles.append({
                        "title": full_title,
                        "start_page": page_num + 1
                    })

        if not detected_articles:
            print("Nie wykryto żadnych artykułów spełniających kryteria.", flush=True)
            return False

        # Krok 2: Ustalanie stron końcowych (end_page)
        for i in range(len(detected_articles)):
            if i < len(detected_articles) - 1:
                detected_articles[i]["end_page"] = detected_articles[i+1]["start_page"] - 1
            else:
                detected_articles[i]["end_page"] = doc.page_count

        # Krok 3: Fizyczne cięcie PDF i zapis do bazy
        print(f"\nWykryto {len(detected_articles)} artykułów. Rozpoczynam cięcie...", flush=True)
        
        for art in detected_articles:
            # Tworzymy unikalną nazwę pliku dla pojedynczego artykułu
            clean_title = "".join([c for c in art["title"] if c.isalnum() or c in (" ", "_", "-")]).strip()[:50]
            output_filename = f"issue_{issue_id}_page_{art['start_page']}_{clean_title.replace(' ', '_')}.pdf"
            output_dir = "/app/shared_data/articles"
            
            # Tworzymy podkatalog na pocięte artykuły, jeśli nie istnieje
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # Wycinanie stron za pomocą PyMuPDF
            art_doc = fitz.open()
            # Strony w PyMuPDF są indeksowane od 0, stąd -1
            art_doc.insert_pdf(doc, from_page=art["start_page"] - 1, to_page=art["end_page"] - 1)
            art_doc.save(output_path)
            art_doc.close()
            
            print(f" -> Wycięto: strony {art['start_page']}-{art['end_page']} | Tytuł: {art['title']}", flush=True)
            
            # Zapis do bazy danych
            new_article = Article(
                issue_id=issue_id,
                title=art["title"],
                author="Nieznany (Do analizy AI)", # Wyciągniemy to w fazie AI
                start_page=art["start_page"],
                end_page=art["end_page"],
                file_path=output_path
            )
            db.add(new_article)
            
        db.commit()
        doc.close()
        return True
        
    except Exception as e:
        print(f"Błąd podczas cięcia PDF: {e}", flush=True)
        return False

def main():
    print("Worker Szczytnik (Silnik tnący) uruchomiony...", flush=True)
    while True:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.status == JobStatus.PENDING).first()
            if job:
                print(f"\n--- Nowe zadanie ID: {job.id} ---", flush=True)
                job.status = JobStatus.PROCESSING
                db.commit()
                
                issue = db.query(Issue).filter(Issue.id == job.issue_id).first()
                success = analyze_and_slice(issue.id, issue.file_path, db)
                
                job.status = JobStatus.COMPLETED if success else JobStatus.FAILED
                db.commit()
                print(f"Zadanie ID: {job.id} sfinalizowane.", flush=True)
        except Exception as e:
            print(f"Błąd krytyczny: {e}", flush=True)
        finally:
            db.close()
        
        time.sleep(10)

if __name__ == "__main__":
    main()