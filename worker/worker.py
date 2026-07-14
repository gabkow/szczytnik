import time
import os
import fitz  # PyMuPDF
import json
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, Enum, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
import enum

# --- KONFIGURACJA ---
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://szczytnik_user:user_secure_password@db/szczytnik_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

try:
    client = genai.Client()
except Exception as e:
    print(f"OSTRZEŻENIE: Problem z inicjalizacją klienta Gemini: {e}", flush=True)

# --- SCHEMAT PYDANTIC DLA GEMINI (GWARANCJA POPRAWNEGO JSON-A) ---
class ArticleMetadata(BaseModel):
    author: str = Field(description="Imię i nazwisko autora. Jeśli nie występuje w tekście, wpisz 'Nieznany'")
    abstract: str = Field(description="Krótkie streszczenie artykułu, maksymalnie 10 zdań.")
    keywords: List[str] = Field(description="Maksymalnie 6 słów kluczowych")

# --- MODELE BAZY DANYCH ---
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

# --- SILNIK AI (Z PYDANTIC I AUTO-RETRY) ---
def extract_metadata_with_ai(text: str, max_retries=2):
    prompt = f"""
    Przeanalizuj poniższy tekst artykułu z czasopisma i wyodrębnij z niego metadane.
    
    Tekst do analizy:
    {text}
    """
    
    for attempt in range(max_retries + 1):
        try:
            # Przekazujemy klasę Pydantic bezpośrednio do response_schema!
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ArticleMetadata,
                )
            )
            
            # W nowym SDK response.parsed zwraca gotowy obiekt klasy ArticleMetadata
            result = response.parsed
            
            if result:
                keywords_str = ", ".join(result.keywords) if isinstance(result.keywords, list) else str(result.keywords)
                return {
                    "author": result.author,
                    "abstract": result.abstract,
                    "keywords": keywords_str
                }
            else:
                # Awaryjne parsowanie tekstu w razie braku response.parsed
                raw_json = json.loads(response.text)
                if isinstance(raw_json.get("keywords"), list):
                    raw_json["keywords"] = ", ".join(raw_json["keywords"])
                return raw_json
            
        except APIError as e:
            if e.code == 429 and attempt < max_retries:
                print(f"    [Ostrzeżenie AI] Przekroczono limit zapytań/tokenów (429). Odczekuję 35 sekund (Próba {attempt+1}/{max_retries})...", flush=True)
                time.sleep(35)
            else:
                print(f"Błąd API Google po {attempt} próbach: {e}", flush=True)
                break
        except Exception as e:
            print(f"Nieoczekiwany błąd komunikacji z AI lub parsowania: {e}", flush=True)
            if attempt < max_retries:
                print(f"    [Ostrzeżenie AI] Próbuję ponownie za 10 sekund (Próba {attempt+1}/{max_retries})...", flush=True)
                time.sleep(10)
            else:
                break
            
    return {"author": "Nieznany", "abstract": "Błąd wygenerowania streszczenia po kilku próbach.", "keywords": ""}

# --- GŁÓWNY ALGORYTM ---
def analyze_and_slice(issue_id, file_path, db):
    try:
        doc = fitz.open(file_path)
        detected_articles = []
        
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
                full_title = " ".join(page_titles)
                if not detected_articles or detected_articles[-1]["start_page"] != page_num + 1:
                    detected_articles.append({"title": full_title, "start_page": page_num + 1})

        if not detected_articles:
            print("Nie wykryto artykułów przy użyciu obecnej heurystyki.", flush=True)
            return False

        for i in range(len(detected_articles)):
            if i < len(detected_articles) - 1:
                detected_articles[i]["end_page"] = detected_articles[i+1]["start_page"] - 1
            else:
                detected_articles[i]["end_page"] = doc.page_count
        
        print(f"\nRozpoczynam cięcie i analizę AI dla {len(detected_articles)} artykułów...", flush=True)
        
        for index, art in enumerate(detected_articles):
            clean_title = "".join([c for c in art["title"] if c.isalnum() or c in (" ", "_", "-")]).strip()[:50]
            output_filename = f"issue_{issue_id}_page_{art['start_page']}_{clean_title.replace(' ', '_')}.pdf"
            output_dir = "/app/shared_data/articles"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_filename)
            
            # Wycinanie fizycznych stron
            art_doc = fitz.open()
            extracted_text = ""
            for p in range(art["start_page"] - 1, art["end_page"]):
                art_doc.insert_pdf(doc, from_page=p, to_page=p)
                extracted_text += doc.load_page(p).get_text("text") + "\n"
                
            art_doc.save(output_path)
            art_doc.close()
            
            print(f" -> [{index+1}/{len(detected_articles)}] Pocięto: {art['title']}. Zapytanie do Gemini API...", flush=True)
            
            ai_data = extract_metadata_with_ai(extracted_text)
            
            print(f"    [AI] Autor: {ai_data.get('author')}", flush=True)
            print(f"    [AI] Słowa kluczowe: {ai_data.get('keywords')}", flush=True)
            
            new_article = Article(
                issue_id=issue_id,
                title=art["title"],
                author=ai_data.get("author", "Nieznany"),
                abstract=ai_data.get("abstract", ""),
                keywords=ai_data.get("keywords", ""),
                start_page=art["start_page"],
                end_page=art["end_page"],
                file_path=output_path
            )
            db.add(new_article)
            db.commit() 
            
            # --- BEZPIECZNIK CZASOWY ---
            if index < len(detected_articles) - 1:
                print("    [Rate Limit] Czekam 20 sekund przed kolejnym zapytaniem...", flush=True)
                time.sleep(20)
            
        doc.close()
        return True
        
    except Exception as e:
        print(f"Błąd krytyczny przy przetwarzaniu PDF: {e}", flush=True)
        return False

def main():
    print("Worker Szczytnik (Silnik tnący + AI Gemini 3.5 Flash + Pydantic Schema + Auto-Retry + 20s Sleep) uruchomiony...", flush=True)
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
            print(f"Błąd bazy: {e}", flush=True)
        finally:
            db.close()
        
        time.sleep(10)

if __name__ == "__main__":
    main()