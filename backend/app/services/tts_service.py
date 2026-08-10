import io
import re
from abc import ABC, abstractmethod

class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """
        Convert text to speech audio bytes.
        """
        pass


class GTTSProvider(TTSProvider):
    async def synthesize(self, text: str) -> bytes:
        from gtts import gTTS
        tts = gTTS(text=text, lang='en', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()


# Factory method for future extensibility
def get_tts_provider() -> TTSProvider:
    return GTTSProvider()

def clean_text_for_tts(text: str) -> str:
    if not text:
        return ""

    # 1. Remove URLs
    text = re.sub(r'http[s]?://\S+', '', text)

    # 2. Remove citations [1], [2][3], [127], [Source 1], etc.
    text = re.sub(r'\[\s*\d+\s*\]', '', text)
    text = re.sub(r'\[\s*Source\s+\d+\s*\]', '', text, flags=re.IGNORECASE)

    # 3. Remove source metadata strings and headers
    source_patterns = [
        r'Sources used[\.:]?', r'Sources[\.:]?', r'Source \d+[\.:]?',
        r'Retrieved from Wikipedia[\.:]?', r'Source data[\.:]?', r'Citations[\.:]?'
    ]
    for pat in source_patterns:
        text = re.sub(pat, '', text, flags=re.IGNORECASE)

    # 4. Convert markdown tables into natural speech
    lines = text.split("\n")
    cleaned_lines = []
    in_table = False
    headers = []
    
    for line in lines:
        line_s = line.strip()
        
        # Remove markdown headers
        if line_s.startswith("#"):
            line_s = re.sub(r'^#+\s*', '', line_s)
            
        # Handle lists: - Item -> Item.
        if line_s.startswith("- ") or line_s.startswith("* "):
            line_s = line_s[2:].strip()
            if not line_s.endswith("."):
                line_s += "."
                
        # Handle Year: XXXX; Film: YYYY
        if "Year:" in line_s and "Film:" in line_s:
            line_s = re.sub(r'Year:\s*(.*?);\s*Film:\s*(.*)', r'In \1, the film was \2.', line_s)
            
        # Tables
        if line_s.startswith("|") and line_s.endswith("|"):
            in_table = True
            cells = [c.strip() for c in line_s.split("|")[1:-1]]
            # If it's a separator line like |---|---|
            if all(all(char == '-' or char == ' ' or char == ':' for char in c) for c in cells if c):
                continue
            
            if not headers:
                headers = cells
                continue
            
            # Data row
            row_speech = []
            for i, cell in enumerate(cells):
                if cell and cell != "-":
                    header = headers[i] if i < len(headers) else ""
                    if header.lower() == "year":
                        row_speech.append(f"In {cell}")
                    elif header.lower() in ("film", "title", "movie"):
                        row_speech.append(f"the film was {cell}")
                    elif header.lower() in ("role", "roles", "character"):
                        row_speech.append(f"playing the roles of {cell}")
                    else:
                        row_speech.append(f"{header} {cell}")
            
            cleaned_lines.append(", ".join(row_speech) + ".")
        else:
            if in_table:
                in_table = False
                headers = []
            cleaned_lines.append(line_s)
            
    text = " ".join(cleaned_lines)

    # 5. Handle year in parentheses: e.g. Sura (2010) -> Sura, released in 2010,
    text = re.sub(r'\(\s*(\d{4})\s*\)', r', released in \1,', text)

    # 6. Remove markdown formatting and symbol characters (*, #, _, `, {}, ~, |, ", “,”,‘,’)
    # Notice: We keep apostrophe (') if inside words (like Vijay's, don't), but remove double quotes and fancy quotes.
    text = re.sub(r'["“”‘’]', '', text)
    text = re.sub(r'[*`_{}~#|]', ' ', text)

    # Replace parentheses and brackets with commas for natural pausing instead of speaking bracket names
    text = re.sub(r'[\(\)\[\]]', ', ', text)
    
    # Remove standalone colons and semicolons that don't belong in speech
    text = text.replace(":", ",")
    text = text.replace(";", ",")
    
    # Clean up multiple commas or punctuation clashes (e.g. , , -> , or , . -> .)
    text = re.sub(r',\s*,+', ',', text)
    text = re.sub(r',\s*\.', '.', text)
    text = re.sub(r'\.\s*\.', '.', text)

    # Replace multiple spaces with a single space and strip leading/trailing commas or spaces
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^,\s*|\s*,$', '', text)
    
    return text
