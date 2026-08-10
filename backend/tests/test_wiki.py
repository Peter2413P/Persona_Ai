import requests
from bs4 import BeautifulSoup
import wikipedia

def test_wiki():
    wiki_page = wikipedia.page("Vijay (actor)", auto_suggest=True)
    wiki_url = wiki_page.url
    
    response = requests.get(wiki_url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    content_div = soup.find('div', {'id': 'mw-content-text'})
    tables = content_div.find_all('table', {'class': 'wikitable'})
    
    print(f"Found {len(tables)} wikitables.")
    if tables:
        rows = tables[0].find_all('tr')
        headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
        print("Headers:", headers)
        
        cells = [td.get_text(strip=True) for td in rows[1].find_all(['th', 'td'])]
        print("First Row:", cells)

if __name__ == "__main__":
    test_wiki()
