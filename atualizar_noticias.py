#!/usr/bin/env python3
"""Atualiza notícias públicas via Google News RSS, sem bibliotecas externas."""
import datetime as dt
import email.utils
import json
import pathlib
import re
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parent
DEST=ROOT/'noticias.json'
QUERIES = [
    '"Associação dos Diplomados da Escola Superior de Guerra" OR site:adesg.org.br OR site:adesgmt.org.br',
    '"Escola Superior de Guerra" Brasil',
    'site:gov.br/defesa "Ministério da Defesa"',
    'site:eb.mil.br "Exército Brasileiro"',
    'site:marinha.mil.br "Marinha do Brasil"',
    'site:fab.mil.br "Força Aérea Brasileira"',
    '"Curso de Estudos de Política e Estratégia" OR "curso de defesa nacional"',
    '"planejamento estratégico" ("Forças Armadas" OR "defesa nacional")',
    '"estratégia nacional de defesa" OR "política nacional de defesa"',
]
OFF_TOPIC = re.compile(r'\bdefesa\W+civil\b|\balerta\s+meteorologico\b')


def is_relevant(item):
    text = f"{item['title']} {item['source']}".casefold()
    text = ''.join(char for char in unicodedata.normalize('NFD', text)
                   if not unicodedata.combining(char))
    return not OFF_TOPIC.search(text)

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; ADESGMT-NewsBot/1.0)'}

def fetch(query):
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=22) as response:
        root=ET.fromstring(response.read())
    for entry in root.findall('./channel/item'):
        title=(entry.findtext('title') or '').strip()
        link=(entry.findtext('link') or '').strip()
        if not title or not link.startswith('https://'):continue
        source_el=entry.find('source')
        source=(source_el.text or '').strip() if source_el is not None else 'Notícias'
        date_str=(entry.findtext('pubDate') or '').strip()
        try:
            date=email.utils.parsedate_to_datetime(date_str).date().isoformat()
        except (TypeError,ValueError,IndexError):date=''
        yield {'title':title,'url':link,'source':source,'date':date}

items=[];seen=set();errors=[]
for query in QUERIES:
    try:
        for item in fetch(query):
            key=item['title'].casefold()
            if key not in seen and is_relevant(item):
                seen.add(key);items.append(item)
    except Exception as exc:errors.append(f'{query}: {exc}')
items.sort(key=lambda item:item['date'],reverse=True)
if not items:
    print('Nenhuma notícia recebida; preservando o arquivo anterior. Erros:',errors)
    raise SystemExit(1)
payload={'updated':dt.datetime.now(dt.timezone.utc).isoformat(),'items':items[:24]}
DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'{len(payload["items"])} notícias salvas. Fontes indisponíveis: {len(errors)}')
