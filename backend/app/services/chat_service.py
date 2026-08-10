import json
from typing import List, Dict, AsyncGenerator
from app.rag.database import get_vector_store
from app.rag.llm import get_llm
from app.db.session import SessionLocal
from app.db.models import StructuredRecord, ExplicitFact, Entity, Persona
from app.services.query_planner import plan_query

async def stream_chat_response(persona_id: str, message: str, history: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    llm = get_llm()
    vector_store = get_vector_store()
    db = SessionLocal()
    
    # Check if persona exists
    persona = db.query(Persona).filter(Persona.id == persona_id).first()
    if not persona:
        db.close()
        yield f"data: {json.dumps({'type': 'error', 'message': 'Persona not found'})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # Generate Query Plan
    plan = plan_query(message, history)
    search_query = plan.get("rewritten_query", message)
    mode = plan.get("mode", "SEMANTIC")
    operation = plan.get("operation", "NONE")
    filters = plan.get("filters", {})
    
    with open("DEBUG_CHROMA.txt", "a") as f:
        f.write(f"\n[QUERY PLAN]\n{json.dumps(plan, indent=2)}\n")
        
    context = ""
    sources = []
    seen_sources = set()

    if mode == "GREETING":
        yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
        system_prompt = "You are PersonaForge AI. Greet the user politely and briefly. Do not mention documents or knowledge bases unless asked."
        prompt = f"{system_prompt}\n\nUser: {message}\nAssistant:"
        try:
            for chunk in llm.stream(prompt):
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        db.close()
        return

    entities = db.query(Entity).filter(Entity.persona_id == persona_id).all()
    entity_ids = [e.id for e in entities]
    
    explicit_context = ""
    
    if mode in ["STRUCTURED", "HYBRID"] and entity_ids:
        # 1. Check Explicit Facts first
        facts_query = db.query(ExplicitFact).filter(ExplicitFact.entity_id.in_(entity_ids))
        
        # We can do generic fuzzy matching on predicate/subject/object based on rewritten_query
        # For a robust system, we query all facts and filter them manually, or use specific SQL filters.
        # Given it's SQLite, let's load facts for the entity and filter in python.
        all_facts = facts_query.all()
        matched_facts = []
        for f in all_facts:
            # simple keyword match against query
            if f.predicate and f.predicate.lower() in search_query.lower():
                matched_facts.append(f)
            elif f.object_val and f.object_val.lower() in search_query.lower():
                matched_facts.append(f)
            elif filters.get("position") and f.position == filters.get("position"):
                matched_facts.append(f)
                
        if matched_facts:
            explicit_context += "Explicit Facts:\n"
            for f in matched_facts:
                explicit_context += f"- {f.subject} -> {f.predicate} -> {f.object_val} (Year: {f.year})\n"
                
        # 2. Check Structured Records
        records_query = db.query(StructuredRecord).filter(StructuredRecord.entity_id.in_(entity_ids))
        all_records = records_query.all()
        
        filtered_records = []
        
        if operation in ["FILTER", "LIST_ALL", "COUNT"]:
            for r in all_records:
                norm = r.normalized_data
                keep = True
                
                rec_year = norm.get("year", 0)
                if filters.get("year") and rec_year != filters.get("year"): keep = False
                if filters.get("year_start") and rec_year < filters.get("year_start"): keep = False
                if filters.get("year_end") and rec_year > filters.get("year_end"): keep = False
                
                if keep and filters.get("keyword"):
                    kw = filters.get("keyword").lower()
                    kw_found = False
                    for k,v in norm.items():
                        if kw in str(v).lower():
                            kw_found = True
                            break
                    if not kw_found: keep = False
                if keep: filtered_records.append(r)
                
        elif operation == "MILESTONE_FILM":
            sorted_records = sorted(all_records, key=lambda x: x.normalized_data.get("year", 0) or x.record_index)
            pos = filters.get("position")
            
            # Explicit flag check first
            if pos == 25:
                explicit = [r for r in sorted_records if r.normalized_data.get("is_25th_film")]
                if explicit: filtered_records.append(explicit[0])
            elif pos == 50:
                explicit = [r for r in sorted_records if r.normalized_data.get("is_50th_film")]
                if explicit: filtered_records.append(explicit[0])
                
            if not filtered_records and pos and 0 < pos <= len(sorted_records):
                filtered_records.append(sorted_records[pos - 1])
                
        elif operation == "FIRST_FILM":
            explicit = [r for r in all_records if r.normalized_data.get("is_first_film")]
            if explicit:
                filtered_records.append(explicit[0])
            else:
                sorted_records = sorted(all_records, key=lambda x: x.normalized_data.get("year", 0) or x.record_index)
                if sorted_records: filtered_records.append(sorted_records[0])
                
        elif operation == "FIRST_LEAD_FILM":
            explicit = [r for r in all_records if r.normalized_data.get("is_first_lead_film")]
            if explicit:
                filtered_records.append(explicit[0])
            else:
                sorted_records = sorted([r for r in all_records if r.normalized_data.get("appearance_type") == "main_role"], key=lambda x: x.normalized_data.get("year", 0) or x.record_index)
                if sorted_records: filtered_records.append(sorted_records[0])
                
        elif operation == "FINAL_FILM":
            explicit = [r for r in all_records if r.normalized_data.get("is_final_film")]
            if explicit:
                filtered_records.append(explicit[-1]) # Use last one if multiple marked
            else:
                sorted_records = sorted(all_records, key=lambda x: x.normalized_data.get("year", 0) or x.record_index)
                if sorted_records: filtered_records.append(sorted_records[-1])
                
        elif operation == "GUEST_APPEARANCES":
            filtered_records = [r for r in all_records if r.normalized_data.get("appearance_type") in ["guest_appearance", "cameo", "extended_cameo", "special_appearance"]]
            
        elif operation == "MULTIPLE_ROLE_FILMS":
            filtered_records = [r for r in all_records if r.normalized_data.get("is_multiple_role") or r.normalized_data.get("role_count", 0) > 1]
            
        elif operation == "ROLE_LOOKUP":
            if filters.get("record_name") or filters.get("keyword"):
                target = (filters.get("record_name") or filters.get("keyword")).lower()
                for r in all_records:
                    title = str(r.normalized_data.get("title", "")).lower()
                    if target in title:
                        filtered_records.append(r)
        
        if filtered_records:
            # Enforce chronological ordering on output
            filtered_records.sort(key=lambda x: x.normalized_data.get("year", 0) or x.record_index)
            
            explicit_context += "\nStructured Records Data:\n"
            if operation == "COUNT":
                explicit_context += f"Total count matching criteria: {len(filtered_records)}\n"
            else:
                for r in filtered_records:
                    explicit_context += f"{json.dumps(r.raw_data)}\n"
                    
            # Add sources
            for r in filtered_records[:10]: # cap sources UI to 10
                s_id = r.source_id
                if s_id not in seen_sources:
                    s_name = r.knowledge_source.name if r.knowledge_source else "Table Data"
                    s_url = r.knowledge_source.source_url if r.knowledge_source else None
                    sources.append({
                        "type": "document",
                        "title": s_name,
                        "content": "Structured Table Record",
                        "url": s_url
                    })
                    seen_sources.add(s_id)

    # 3. Semantic Retrieval (Fallback or HYBRID)
    semantic_context = ""
    if mode in ["SEMANTIC", "HYBRID"] or not explicit_context:
        try:
            docs_and_scores = vector_store.similarity_search_with_score(search_query, k=5, filter={"persona_id": persona_id})
            valid_docs = [d for d in docs_and_scores if d[1] < 1.8]
            
            for doc, score in valid_docs:
                semantic_context += doc.page_content + "\n\n"
                source_title = doc.metadata.get("source_name", "Unknown Document")
                if source_title not in seen_sources:
                    sources.append({
                        "type": doc.metadata.get("source_type", "document"),
                        "title": source_title,
                        "content": doc.page_content[:200] + "...",
                        "url": doc.metadata.get("source_url", None)
                    })
                    seen_sources.add(source_title)
        except Exception as e:
            with open("DEBUG_CHROMA.txt", "a") as f:
                f.write(f"SEMANTIC EXCEPTION: {e}\n")

    context = explicit_context + "\n" + semantic_context

    yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
    
    if not context.strip():
        msg = "I couldn't find this information in the knowledge sources provided for this persona."
        yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        db.close()
        return

    # Formatting Prompt
    system_prompt = "You are a helpful AI assistant representing a specific persona. Answer the user's question based strictly on the provided Context.\n"
    
    if mode == "STRUCTURED":
        system_prompt += "The Context contains exactly extracted explicit facts and structured data rows. Format your answer directly and clearly using this data. Do not hallucinate or invent records not in the context.\n"
        if operation == "LIST_ALL":
            system_prompt += "Present the data as a clean Markdown table.\n"
    else:
        system_prompt += "Do not invent facts not supported by the context.\n"
        
    prompt = f"{system_prompt}\nContext:\n{context}\n\nQuestion: {message}\nAnswer:"
    
    try:
        for chunk in llm.stream(prompt):
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
    db.close()

