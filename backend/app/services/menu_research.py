"""Refresh cached menu descriptions from the official site, never local prices."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

from app.db.catalog import load_catalog
from app.services.menu_evidence import validate_evidence
from app.services.llm_direct import DEFAULT_EVIDENCE

SITE = 'https://www.mega-mgccoffee.com/menu/menu.php?page='
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def has_class(self, value): return value in self.attrs.get('class', '').split()

    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(c.text() if isinstance(c, Node) else c for c in self.children)).strip()

    def find(self, predicate):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if predicate(child): result.append(child)
                result.extend(child.find(predicate))
        return result


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID: self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data): self.stack[-1].children.append(data)


def parse_page(html, source):
    parser = Tree()
    parser.feed(html)
    lists = parser.root.find(lambda n: n.tag == 'ul' and n.attrs.get('id') == 'menu_list')
    if len(lists) != 1: raise ValueError('Official menu list layout changed')
    records = []
    for item in lists[0].children:
        if not isinstance(item, Node) or item.tag != 'li': continue
        modal = item.find(lambda n: n.has_class('inner_modal'))
        labels = item.find(lambda n: n.has_class('cont_gallery_list_label'))
        images = item.find(lambda n: n.tag == 'img')
        if len(modal) != 1 or not labels or not images: continue
        title = modal[0].find(lambda n: n.has_class('inner_modal_title'))
        boxes = [n for n in modal[0].children if isinstance(n, Node) and n.has_class('cont_text_box')]
        if not title or not boxes: continue
        names = title[0].find(lambda n: n.tag == 'b')
        blocks = [n for n in boxes[0].children if isinstance(n, Node) and n.has_class('cont_text')]
        if not names or len(blocks) < 3: raise ValueError('Official description layout changed')
        temperature = {'ICE': 'COLD', 'HOT': 'HOT'}.get(labels[0].text())
        if temperature is None: continue
        text = blocks[2].text()
        if not text: raise ValueError('Empty official description')
        records.append({'official_name': names[0].text(), 'temperature': temperature,
                        'image_source_url': images[0].attrs.get('src'), 'description': text,
                        'source': source, 'page_sha256': hashlib.sha256(html.encode()).hexdigest()})
    return records


def fetch_page(page):
    source = SITE + str(page)
    request = Request(source, headers={'User-Agent': 'Hackaton-menu-research/1.0'})
    with urlopen(request, timeout=30) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000: raise ValueError('Official page too large')
    return parse_page(raw.decode('utf-8'), source)


def build_cache(existing, images, image_sources, pages, checked_date):
    """Match curated official name + temperature + exact original image URL."""
    result = json.loads(json.dumps(existing, ensure_ascii=False))
    by_image = {(s['image_path'], s['temperature']): s for s in image_sources}
    audit = {'checked_date': checked_date, 'source_kind': 'official_website',
             'local_price_or_category_changes': False, 'matched': [], 'unmatched': []}
    normalize = lambda text: re.sub(r'\s+', '', text)
    for menu in result['menus']:
        for temp, fields in menu['variants'].items():
            provenance = by_image.get((images[menu['name']][temp], temp))
            matches = [r for r in pages if provenance and r['temperature'] == temp
                       and normalize(r['official_name']) == normalize(provenance['official_name'])
                       and r['image_source_url'] == provenance['image_source_url']]
            if len(matches) != 1:
                # Never silently retain a description whose identity can no longer be verified.
                fields['description'] = {'status': 'unknown', 'value': None, 'source': None,
                    'checked_date': None, 'note': 'Current official name/temperature/image identity was not uniquely matched.'}
                audit['unmatched'].append({'menu_id': menu['menu_id'], 'temperature': temp})
                continue
            record = matches[0]
            menu['official_name'] = record['official_name']
            menu['mapping_note'] = '기존 이미지 출처의 공식명·온도·원본 이미지 URL이 현재 공식 페이지와 일치함. 가격·분류는 로컬 데이터를 유지함.'
            fields['description'] = {'status': 'verified', 'value': record['description'],
                'source': record['source'], 'checked_date': checked_date,
                'note': 'Official base-menu description; additional order options are excluded. Not a measured taste score.'}
            audit['matched'].append({k: record[k] for k in ('official_name', 'temperature', 'source', 'image_source_url', 'page_sha256')} | {'menu_id': menu['menu_id']})
    return result, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pages', type=int, default=12)
    parser.add_argument('--output', type=Path, required=True, help='New output file; no overwrite')
    parser.add_argument('--audit', type=Path, required=True, help='New audit file; no overwrite')
    args = parser.parse_args()
    if args.pages < 1 or args.pages > 30: parser.error('Page count must be 1..30')
    if args.output.resolve() == args.audit.resolve(): parser.error('Output and audit must be different files')
    if args.output.exists() or args.audit.exists(): parser.error('Use new output paths')
    common = DEFAULT_EVIDENCE.parent
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = sum(list(pool.map(fetch_page, range(1, args.pages + 1))), [])
    data, audit = build_cache(json.loads(DEFAULT_EVIDENCE.read_text(encoding='utf-8')),
        json.loads((common / 'menu_images.json').read_text(encoding='utf-8')),
        json.loads((common / 'menu_image_sources.json').read_text(encoding='utf-8')),
        records, date.today().isoformat())
    validate_evidence(data, load_catalog())
    for path, value in [(args.output, data), (args.audit, audit)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream: json.dump(value, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'matched_variants': len(audit['matched']), 'unmatched': audit['unmatched']}, ensure_ascii=False))


if __name__ == '__main__': main()
