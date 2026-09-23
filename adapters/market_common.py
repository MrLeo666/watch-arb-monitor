"""Helpers for opt-in market pilots; missing structure is an error, never success."""
import json
import math
import requests
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'}

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=35)
    r.raise_for_status()
    return r.text

def page_data(html):
    script = BeautifulSoup(html, 'html.parser').find('script', id='__NEXT_DATA__')
    if script is None:
        raise ValueError('Expected public catalogue data missing')
    return json.loads(script.string)['props']['pageProps']

def amount(value):
    if isinstance(value, dict):
        value = value.get('amount')
    try:
        n = float(value)
        return n if math.isfinite(n) and n > 0 else None
    except (ValueError, TypeError):
        return None
