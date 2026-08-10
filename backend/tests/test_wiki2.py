import requests
from bs4 import BeautifulSoup

def test_wiki():
    url = "https://en.wikipedia.org/wiki/Vijay_(actor)"
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    content_div = soup.find('div', {'id': 'mw-content-text'})
    tables = content_div.find_all('table', {'class': 'wikitable'})
    
    print(f"Found {len(tables)} wikitables on main page.")
    
    url_film = "https://en.wikipedia.org/wiki/Vijay_filmography"
    response = requests.get(url_film, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    content_div = soup.find('div', {'id': 'mw-content-text'})
    tables = content_div.find_all('table', {'class': 'wikitable'})
    print(f"Found {len(tables)} wikitables on filmography page.")
    
if __name__ == "__main__":
    test_wiki()
