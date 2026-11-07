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
    'site:adesg.org.br',
    '"ADESG Nacional" OR "Associação dos Diplomados da Escola Superior de Guerra"',
    '"Escola Superior de Guerra" Brasil',
    '"Escola Superior de Defesa" Brasil',
    'site:gov.br/defesa "Ministério da Defesa"',
    'site:eb.mil.br "Exército Brasileiro"',
    'site:marinha.mil.br "Marinha do Brasil"',
    'site:fab.mil.br "Força Aérea Brasileira"',
    '"Curso de Estudos de Política e Estratégia" OR "curso de defesa nacional"',
    '"planejamento estratégico" ("Forças Armadas" OR "defesa nacional")',
    '"estratégia nacional de defesa" OR "política nacional de defesa"',
    'geopolítica (Brasil OR "América do Sul" OR "Atlântico Sul")',
    '"soberania nacional" (Brasil OR Amazônia OR fronteiras)',
    '"inteligência artificial" ("defesa nacional" OR "Forças Armadas" OR "tecnologia militar")',
    '"tecnologia de defesa" OR "base industrial de defesa" OR "indústria de defesa"',
    '"defesa cibernética" OR "soberania digital" Brasil',
    '"segurança internacional" (Brasil OR "América do Sul" OR "Atlântico Sul")',
    '"vigilância de fronteiras" Brasil OR "segurança marítima" Brasil',
]
OFF_TOPIC = re.compile(r'\bdefesa\W+civil\b|\balertas?\s+meteorologicos?\b|\badesg\W+(?:mt|mato grosso)\b|\bdelegacia(?:\s+regional)?\s+(?:de\s+)?mato grosso\b|adesgmt\.org\.br')


def is_relevant(item):
    text = f"{item['title']} {item['source']} {item.get('source_url', '')}".casefold()
    text = ''.join(char for char in unicodedata.normalize('NFD', text)
                   if not unicodedata.combining(char))
    return not OFF_TOPIC.search(text)

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; ADESGMT-NewsBot/1.0)'}

def fetch(query):
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':f'({query}) -"Defesa Civil" -site:adesgmt.org.br','hl':'pt-BR','gl':'BR','ceid':'BR:pt-419'})
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=22) as response:
        root=ET.fromstring(response.read())
    for entry in root.findall('./channel/item'):
        title=(entry.findtext('title') or '').strip()
        link=(entry.findtext('link') or '').strip()
        if not title or not link.startswith('https://'):continue
        source_el=entry.find('source')
        source=(source_el.text or '').strip() if source_el is not None else 'Notícias'
        source_url=source_el.get('url', '') if source_el is not None else ''
        date_str=(entry.findtext('pubDate') or '').strip()
        try:
            date=email.utils.parsedate_to_datetime(date_str).date().isoformat()
        except (TypeError,ValueError,IndexError):date=''
        yield {'title':title,'url':link,'source':source,'date':date,'source_url':source_url}

items=[];seen=set();errors=[]
for query in QUERIES:
    try:
        for item in fetch(query):
            relevant = is_relevant(item)
            item.pop('source_url', None)
            key=item['title'].casefold()
            if key not in seen and relevant:
                seen.add(key);items.append(item)
    except Exception as exc:errors.append(f'{query}: {exc}')
items.sort(key=lambda item:item['date'],reverse=True)
if not items:
    print('Nenhuma notícia recebida; preservando o arquivo anterior. Erros:',errors)
    raise SystemExit(1)
payload={'updated':dt.datetime.now(dt.timezone.utc).isoformat(),'items':items[:24]}
DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'{len(payload["items"])} notícias salvas. Fontes indisponíveis: {len(errors)}')
