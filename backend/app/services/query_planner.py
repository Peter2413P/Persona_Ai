import json
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

def plan_query(message: str, history: list) -> dict:
    """
    Generate a query plan for the given message.
    """
    llm = get_llm()
    
    # 1. Standalone Query Rewrite
    if history:
        history_text = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in history[-4:]])
        rewrite_prompt = PromptTemplate(
            input_variables=["history", "question"],
            template="""Rewrite the question to be a standalone query resolving all pronouns.
History:
{history}
User Question: {question}
Rewritten Question:"""
        )
        rewritten = llm.invoke(rewrite_prompt.format(history=history_text, question=message)).strip()
        if rewritten.startswith('"') and rewritten.endswith('"'):
            rewritten = rewritten[1:-1]
    else:
        rewritten = message
        
    # 2. Query Planning
    plan_prompt = PromptTemplate(
        input_variables=["question"],
        template="""Analyze the following user question and output a JSON object representing the Query Plan.
You must return ONLY valid JSON.

Query Modes:
- STRUCTURED (for exact factual lookups: dates, specific positions, counting, filtering)
- SEMANTIC (for prose, "why", "how", biographical details)
- HYBRID (for a mix of both)
- GREETING (for hello, hi, how are you)

Operations (if STRUCTURED/HYBRID):
- FILTER (e.g. movies in 1995)
- FIRST_FILM (e.g. first movie, debut)
- FIRST_LEAD_FILM (e.g. first movie as lead actor)
- FINAL_FILM (e.g. last movie, final film)
- MILESTONE_FILM (e.g. 25th film, 50th film)
- GUEST_APPEARANCES (e.g. guest appearance, cameo, special appearance)
- MULTIPLE_ROLE_FILMS (e.g. multiple roles, dual roles, triple roles)
- ROLE_LOOKUP (e.g. exact role in a specific movie)
- COUNT (e.g. how many movies)
- LIST_ALL (e.g. complete filmography)

Filters object can contain:
- year (int)
- year_start (int)
- year_end (int)
- keyword (string)
- target_entity (string)
- record_name (string)

JSON Schema:
{{
  "mode": "STRUCTURED | SEMANTIC | HYBRID | GREETING",
  "operation": "FILTER | FIRST_FILM | FIRST_LEAD_FILM | FINAL_FILM | MILESTONE_FILM | GUEST_APPEARANCES | MULTIPLE_ROLE_FILMS | ROLE_LOOKUP | COUNT | LIST_ALL | NONE",
  "filters": {{
      "year": null,
      "year_start": null,
      "year_end": null,
      "keyword": null,
      "target_entity": null,
      "record_name": null,
      "position": null
  }}
}}

Question: {question}
"""
    )
    
    response = llm.invoke(plan_prompt.format(question=rewritten))
    
    try:
        plan = json.loads(_clean_json_output(response))
        plan["rewritten_query"] = rewritten
        return plan
    except Exception as e:
        print("Plan Parsing Error:", e)
        return {
            "mode": "SEMANTIC",
            "operation": "NONE",
            "filters": {},
            "rewritten_query": rewritten
        }
