#!/usr/bin/env python3
"""Atualiza notícias públicas via Google News RSS, sem bibliotecas externas."""
import datetime as dt
import email.utils
import json
import pathlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parent
DEST=ROOT/'noticias.json'
QUERIES=[
    'site:gov.br/defesa defesa nacional',
    'site:eb.mil.br Exército Brasileiro',
    'site:marinha.mil.br Marinha do Brasil',
    'site:fab.mil.br Força Aérea Brasileira',
    'Escola Superior de Guerra defesa estratégia Brasil',
]
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
            if key not in seen:
                seen.add(key);items.append(item)
    except Exception as exc:errors.append(f'{query}: {exc}')
items.sort(key=lambda item:item['date'],reverse=True)
if not items:
    print('Nenhuma notícia recebida; preservando o arquivo anterior. Erros:',errors)
    raise SystemExit(1)
payload={'updated':dt.datetime.now(dt.timezone.utc).isoformat(),'items':items[:24]}
DEST.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'{len(payload["items"])} notícias salvas. Fontes indisponíveis: {len(errors)}')
