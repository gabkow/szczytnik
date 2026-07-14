import time
import os
import fitz  # PyMuPDF
import json
from google import genai
from google.genai import types
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

# --- SILNIK AI ---
def extract_metadata_with_ai(text: str):
    try:
        prompt = f"""
        Przeanalizuj poniższy tekst artykułu z czasopisma i zwróć metadane w formacie JSON.
        Wymagana struktura JSON:
        {{
            "author": "Imię i nazwisko autora. Jeśli nie występuje w tekście, wpisz 'Nieznany'",
            "abstract": "Krótkie streszczenie artykułu, maksymalnie 10 zdań.",
            "keywords": ["słowo1", "słowo2", "słowo3"] (maksymalnie 6 słów kluczowych)
        }}
        
        Tekst do analizy:
        {text}
        """
        
        # Używamy najnowszego modelu dostępnego dla nowych kluczy API
        response = client.models.generate_content(
            model='gemini-3.5-flash',  # <--- ZMIANA NA NAJNOWSZĄ GENERACJĘ
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        result = json.loads(response.text)
        
        if isinstance(result.get("keywords"), list):
            result["keywords"] = ", ".join(result["keywords"])
            
        return result
    except Exception as e:
        print(f"Błąd komunikacji z AI: {e}", flush=True)
        return {"author": "Nieznany", "abstract": "Błąd wygenerowania streszczenia.", "keywords": ""}

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
            
            # Wysłanie tekstu do AI
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
            db.commit() # Zapisujemy artykuł od razu, by nie czekać na całą serię!
            
            # --- BEZPIECZNIK CZASOWY (RATE LIMITING) ---
            # Jeśli to nie jest ostatni artykuł na liście, czekamy 13 sekund w obronie przed limitem 5 RPM
            if index < len(detected_articles) - 1:
                print("    [Rate Limit] Czekam 13 sekund przed kolejnym zapytaniem...", flush=True)
                time.sleep(13)
            
        doc.close()
        return True
        
    except Exception as e:
        print(f"Błąd krytyczny przy przetwarzaniu PDF: {e}", flush=True)
        return False

def main():
    print("Worker Szczytnik (Silnik tnący + AI Gemini 3 Flash + Rate Limiting) uruchomiony...", flush=True)
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