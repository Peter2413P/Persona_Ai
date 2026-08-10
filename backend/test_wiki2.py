import asyncio
from app.services.research_service import fetch_url_content

title, text, records = fetch_url_content("https://en.wikipedia.org/wiki/Vijay_filmography")
print(f"Title: {title}")
print(f"Total structured records: {len(records)}")
if len(records) > 0:
    for i in range(5):
        if i < len(records):
            print(records[i])
