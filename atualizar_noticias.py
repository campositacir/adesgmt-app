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


TOPICS = re.compile(
    r'\b(?:adesg|esg|escola superior de (?:guerra|defesa)|'
    r'associacao dos diplomados da escola superior de guerra|'
    r'curso de estudos de politica e estrategia|ministerio da defesa|'
    r'forcas? armadas?|exercito|marinha|aeronautica|forca aerea|'
    r'geopolitic[ao]s?|defesa nacional|(?:estrategia|politica) nacional de defesa|estrategia militar|'
    r'planejamento estrategico|tecnologias? de defesa|tecnologia militar|'
    r'industria de defesa|base industrial de defesa|defesa cibernetica|'
    r'soberania digital|seguranca internacional|seguranca maritima|'
    r'vigilancia de fronteiras|exercicio militar|treinamento de guerra|'
    r'robos terrestres|operacao militar)\b'
)
SOVEREIGNTY = re.compile(r'\bsoberania\b')
STRATEGIC_CONTEXT = re.compile(r'\b(?:defesa|fronteiras?|amazonia|atlantico sul|territorial|militar)\b')
SOCIAL_SOURCES = {'instagram', 'facebook', 'tiktok', 'x', 'twitter', 'threads', 'youtube'}
OFFICIAL_DOMAINS = {'adesg.org.br', 'eb.mil.br', 'marinha.mil.br', 'fab.mil.br'}
STOP_WORDS = {'para', 'sobre', 'entre', 'apos', 'como', 'mais', 'pelo', 'pela', 'pelos', 'pelas', 'este', 'esta'}


def normalize(text):
    return ''.join(char for char in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(char))


def headline(item):
    suffix = ' - ' + item['source']
    title = item['title']
    return normalize(title.removesuffix(suffix))


def is_relevant(item):
    title = headline(item)
    source = normalize(item['source'])
    source_url = urllib.parse.urlsplit(item.get('source_url', ''))
    host = source_url.hostname or ''
    if OFF_TOPIC.search(f"{title} {source} {host}") or source in SOCIAL_SOURCES:
        return False
    if re.search(r'\b(?:enem|gabarito)\b', title):
        return False
    official = any(host == domain or host.endswith('.' + domain) for domain in OFFICIAL_DOMAINS)
    official_defense = host in {'gov.br', 'www.gov.br'} and source_url.path.startswith('/defesa')
    sovereignty = SOVEREIGNTY.search(title) and STRATEGIC_CONTEXT.search(title)
    return bool(official or official_defense or TOPICS.search(title) or sovereignty)


def select_news(items, limit=24):
    selected = []
    seen = []
    for item in sorted(items, key=lambda item: item['date'], reverse=True):
        if not is_relevant(item):
            continue
        title = headline(item)
        words = set(re.findall(r'\b\w{4,}\b', title)) - STOP_WORDS
        if any(title == previous or
               (len(words & previous_words) >= 4 and
                len(words & previous_words) / len(words | previous_words) >= 0.65)
               for previous, previous_words in seen):
            continue
        seen.append((title, words))
        selected.append({key: value for key, value in item.items() if key != 'source_url'})
        if len(selected) == limit:
            break
    return selected

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

def main():
    candidates = []
    errors = []
    for query in QUERIES:
        try:
            candidates.extend(fetch(query))
        except (OSError, ET.ParseError) as exc:
            errors.append(f'{query}: {exc}')
    items = select_news(candidates)
    if not items:
        print('Nenhuma notícia relevante recebida; preservando o arquivo anterior. Erros:', errors)
        raise SystemExit(1)
    payload = {'updated': dt.datetime.now(dt.timezone.utc).isoformat(), 'items': items}
    DEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(items)} notícias salvas. Buscas indisponíveis: {len(errors)}')


if __name__ == '__main__':
    main()
