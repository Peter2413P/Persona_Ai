import json
import re
from app.rag.llm import get_llm
from langchain_core.prompts import PromptTemplate

def _clean_json_output(result: str) -> str:
    result = result.strip()
    if result.startswith("```json"):
        result = result[7:]
    elif result.startswith("```"):
        result = result[3:]
    if result.endswith("```"):
        result = result[:-3]
    return result.strip()

def detect_entity(source_title: str, content: str) -> dict:
    """
    Detect the primary entity this document is about.
    """
    llm = get_llm()
    prompt = PromptTemplate(
        input_variables=["title", "content"],
        template="""You are an AI tasked with identifying the primary entity (person, organization, etc.) that a document is about.
Return a valid JSON object with EXACTLY this structure:
{{
  "entity_name": "Primary Name",
  "aliases": ["Alias 1", "Alias 2"]
}}

Document Title: {title}
Document Snippet:
{content}
"""
    )
    # Give it the first 2000 chars to avoid context limits
    snippet = content[:2000] if content else source_title
    response = llm.invoke(prompt.format(title=source_title, content=snippet))
    
    try:
        data = json.loads(_clean_json_output(response))
        return {
            "entity_name": data.get("entity_name", "Unknown"),
            "aliases": data.get("aliases", [])
        }
    except Exception as e:
        print("Failed to detect entity:", e)
        return {"entity_name": "Unknown", "aliases": []}

def detect_dataset_schema(entity_name: str, headers: list, sample_rows: list) -> dict:
    """
    Detect what a table represents (e.g. filmography, sports_stats).
    """
    llm = get_llm()
    prompt = PromptTemplate(
        input_variables=["entity", "headers", "rows"],
        template="""Analyze this table about '{entity}' and determine its schema.
Return a valid JSON object with EXACTLY this structure:
{{
  "dataset_type": "string (e.g., filmography, awards, sports_statistics, career_timeline)",
  "primary_fields": ["list of column names that uniquely identify a row, e.g. year, title"],
  "attributes": ["list of descriptive columns, e.g. role, notes"],
  "sortable_fields": ["columns that can be sorted, e.g. year"],
  "filterable_fields": ["columns that can be filtered, e.g. year, role"],
  "semantic_flags": ["list of explicit flags e.g. is_final_film, is_first_film, is_guest_appearance, is_cameo, is_multiple_role"]
}}

Table Headers: {headers}
Sample Rows (up to 3):
{rows}
"""
    )
    response = llm.invoke(prompt.format(
        entity=entity_name, 
        headers=json.dumps(headers),
        rows=json.dumps(sample_rows[:3])
    ))
    
    try:
        data = json.loads(_clean_json_output(response))
        return {
            "dataset_type": data.get("dataset_type", "generic_table"),
            "primary_fields": data.get("primary_fields", headers[:2]),
            "attributes": data.get("attributes", headers[2:]),
            "sortable_fields": data.get("sortable_fields", []),
            "filterable_fields": data.get("filterable_fields", []),
            "semantic_flags": data.get("semantic_flags", [])
        }
    except Exception as e:
        print("Failed to detect schema:", e)
        return {
            "dataset_type": "generic_table",
            "primary_fields": headers[:2] if len(headers) >= 2 else headers,
            "attributes": headers[2:] if len(headers) >= 3 else [],
            "sortable_fields": [],
            "filterable_fields": [],
            "semantic_flags": []
        }

def normalize_table_records(dataset_type: str, records: list) -> list:
    """
    Convert raw string records into normalized fields using robust generic heuristics.
    """
    normalized = []
    
    for idx, rec in enumerate(records):
        norm = {}
        # Keep original data
        for k, v in rec.items():
            norm[k] = v
            
            val = str(v).strip()
            key_lower = k.lower()
            val_lower = val.lower()
            
            # Numeric conversion
            if "year" in key_lower or "season" in key_lower:
                match = re.search(r'\d{4}', val)
                if match:
                    norm["year"] = int(match.group())
                else:
                    norm["year"] = 0
            
            # Array conversion for roles/categories
            if "role" in key_lower or "category" in key_lower:
                # Robustly split roles considering parentheses, e.g. "Name (Alias)"
                # First replace commas inside parens with a placeholder if needed, 
                # but simple split on commas and common delimiters is usually enough 
                # for basic parsing unless nested deeply. Let's do a smart split.
                parts = [p.strip() for p in re.split(r',|;|/|\band\b|&', val) if p.strip()]
                norm["roles"] = parts
                norm["role_count"] = len(parts)
                norm["is_multiple_role"] = len(parts) > 1
                
            # Semantic Flags from Notes/Roles
            if "note" in key_lower or "role" in key_lower or "title" in key_lower:
                if "guest" in val_lower:
                    norm["appearance_type"] = "guest_appearance"
                    norm["is_guest_appearance"] = True
                elif "extended cameo" in val_lower:
                    norm["appearance_type"] = "extended_cameo"
                    norm["is_extended_cameo"] = True
                elif "cameo" in val_lower:
                    norm["appearance_type"] = "cameo"
                    norm["is_cameo"] = True
                elif "special appearance" in val_lower:
                    norm["appearance_type"] = "special_appearance"
                elif "child" in val_lower:
                    norm["appearance_type"] = "child_actor"
                    norm["is_child_actor"] = True
                    
                if "first film" in val_lower and "lead" not in val_lower:
                    norm["is_first_film"] = True
                if "first film as lead" in val_lower or "debut as lead" in val_lower:
                    norm["is_first_lead_film"] = True
                if "25th film" in val_lower:
                    norm["is_25th_film"] = True
                if "50th film" in val_lower:
                    norm["is_50th_film"] = True
                if "final film" in val_lower or "last film" in val_lower:
                    norm["is_final_film"] = True
                    
        if "appearance_type" not in norm:
            norm["appearance_type"] = "main_role"
            
        normalized.append(norm)
    return normalized

def extract_explicit_facts(entity_name: str, content: str) -> list:
    """
    Extract key explicit facts (milestones, debuts, etc) directly from text.
    """
    llm = get_llm()
    prompt = PromptTemplate(
        input_variables=["entity", "content"],
        template="""Extract explicit career facts, debuts, and milestones about '{entity}' from the text.
Return a valid JSON object containing a "facts" array. Each fact must have:
{{
  "facts": [
    {{
      "subject": "Name of the entity",
      "predicate": "relation (e.g., lead_actor_debut, first_film, nth_film, award_won)",
      "object": "target of relation (e.g., film name, award name)",
      "year": 1992,
      "position": 50 (if applicable, e.g. for 50th film. otherwise null)
    }}
  ]
}}

Text:
{content}
"""
    )
    
    snippet = content[:3000]
    response = llm.invoke(prompt.format(entity=entity_name, content=snippet))
    
    try:
        data = json.loads(_clean_json_output(response))
        return data.get("facts", [])
    except Exception as e:
        print("Failed to extract facts:", e)
        return []
