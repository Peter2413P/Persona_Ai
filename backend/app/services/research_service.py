import requests
from bs4 import BeautifulSoup
from app.db.session import SessionLocal
from app.db.models import KnowledgeSource
from app.services.knowledge_service import process_knowledge_source

def fetch_url_content(url: str) -> tuple[str, str, list[dict]]:
    """Fetch URL, extract text using BeautifulSoup, and preserve Wikipedia tables."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.extract()
        
    title = soup.title.string if soup.title else url
    full_text = f"--- {title} ---\n\n"
    structured_records = []
    
    is_wikipedia = "wikipedia.org" in url
    
    if is_wikipedia:
        # Extract main paragraphs first
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                full_text += text + "\n\n"
                
        # Extract tables (e.g. filmography, awards)
        tables = soup.find_all('table', {'class': 'wikitable'})
        for table in tables:
            rows = table.find_all('tr')
            if not rows:
                continue
            
            headers_list = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
            
            # Process ANY wikitable
            
            for row in rows[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all(['th', 'td'])]
                
                actual_cells = cells.copy()
                if len(actual_cells) < len(headers_list):
                    diff = len(headers_list) - len(actual_cells)
                    actual_cells = [""] * diff + actual_cells
                
                record = {}
                import re
                
                for i, cell in enumerate(actual_cells):
                    if i < len(headers_list):
                        header = headers_list[i].lower()
                        clean_cell = re.sub(r'\[[a-zA-Z0-9]+\]', '', cell).strip()
                        norm_header = re.sub(r'[^a-zA-Z0-9_]', '_', header).strip('_')
                        if norm_header:
                            record[norm_header] = clean_cell
                                
                if not record.get("year") and structured_records:
                    record["year"] = structured_records[-1].get("year", "")
                    
                if record:
                    structured_records.append(record)
                
                cell_texts = []
                for i, cell in enumerate(cells):
                    header = headers_list[i] if i < len(headers_list) else f"Column_{i}"
                    cell_texts.append(f"{header}: {cell}")
                
                if cell_texts:
                    full_text += " | ".join(cell_texts) + "\n"
            full_text += "\n"
    else:
        full_text += soup.get_text(separator='\n', strip=True)
        
    return title, full_text, structured_records

def ingest_url_background(source_id: str, url: str):
    try:
        title, text, structured_records = fetch_url_content(url)
        process_knowledge_source(
            source_id=source_id,
            text_content=text,
            metadata={"source_title": title, "url": url},
            raw_records=structured_records
        )
    except Exception as e:
        db = SessionLocal()
        source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
        if source:
            source.status = "FAILED"
            source.error_message = f"URL Fetch Error: {str(e)}"
            db.commit()
        db.close()
