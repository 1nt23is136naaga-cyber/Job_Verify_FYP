import re
content = open('scraper2.py', encoding='utf-8').read()
# Find class names and function names that hint at site support
classes = re.findall(r'class\s+(\w+Scraper|\w+Spider|\w+Parser)', content)
print("Scraper classes:", classes)
# Find site-related strings
sites = re.findall(r'["\']https?://(?:www\.)?([a-zA-Z0-9\-]+\.(?:com|in|co\.in|io|net))[/"\']', content)
print("Domains found:", sorted(set(sites)))
# Also search for def scrape_ functions
funcs = re.findall(r'def (scrape_\w+|parse_\w+|fetch_\w+)', content)
print("Scraper functions:", funcs)
