"""Parse publicly embedded product data. No network requests in this module."""
import json
import re
from datetime import datetime, timezone
from lxml import html

def now():
    return datetime.now(timezone.utc).isoformat()

def text_from_html(markup):
    doc=html.fragment_fromstring(markup or '<p></p>',create_parent='div')
    for e in doc.xpath('.//script|.//style|.//noscript'):e.drop_tree()
    for e in doc.iter():
        if e.text:e.text=re.sub(r'\s+',' ',e.text)
        if e.tail:e.tail=re.sub(r'\s+',' ',e.tail)
    for e in doc.xpath('.//p|.//li|.//h1|.//h2|.//h3|.//h4|.//div|.//br'):
        e.tail='\n'+(e.tail or '')
    return '\n'.join(x.strip() for x in doc.text_content().splitlines() if x.strip())

def extract_labeled(text, label):
    lines=text.splitlines()
    for i,line in enumerate(lines):
        match=re.match(label+r'\s*(?::|$)',line,re.I)
        if match:
            return line[match.end():].strip() or (lines[i+1] if i+1<len(lines) else None)
    return None

def parse_product(markup, url):
    tree=html.fromstring(markup)
    nodes=tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if not nodes:raise ValueError('Missing public __NEXT_DATA__; website structure changed')
    state=json.loads(nodes[0])['props']['pageProps']['initialReduxState']
    queries=state.get('productsApi',{}).get('queries',{})
    product=next((q['data'] for k,q in queries.items() if k.startswith('getByIdProducts(') and isinstance(q.get('data'),dict)),None)
    if not product or not product.get('id'):raise ValueError('No product object in this page')
    details=product.get('detail') or []
    vi=next((d for d in details if d.get('langCode')=='vi'),details[0] if details else {})
    description=text_from_html(vi.get('htmlDescription'))
    label=lambda pattern:extract_labeled(description,pattern)
    brand_elements=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," brand-name ")]')
    brand=next((e.text_content().strip() for e in brand_elements if e.text_content().strip()),None)
    name=vi.get('name') or (product.get('graphData') or {}).get('title')
    sizes=re.findall(r'(?<!\d)(\d+(?:[.,]\d+)?)\s*(ml|g|kg|l)\b',name or '',re.I)
    row={
        'product_id':str(product['id']),'sku':product.get('sku'),'name':name,
        'brand_explicit':brand,'category_slug':(product.get('productType') or {}).get('slug'),
        'origin_label_raw':(product.get('graphData') or {}).get('origin'),
        'brand_origin_explicit':label(r'(?:Xuất xứ thương hiệu|Nguồn gốc thương hiệu)'),
        'manufactured_in_explicit':label(r'(?:Sản xuất tại|Nơi sản xuất|Xuất xứ sản phẩm)'),
        'size_from_name':sizes,'current_price_vnd':product.get('currentPrice'),
        'min_price_vnd':product.get('minPrice'),'max_price_vnd':product.get('maxPrice'),
        'min_price_before_discount_vnd':product.get('minPriceBeforeDiscount'),
        'max_price_before_discount_vnd':product.get('maxPriceBeforeDiscount'),
        'benefits_labeled':label(r'(?:Công dụng(?: chính)?|Ưu điểm(?: nổi bật)?(?: của [^:]+)?)'),
        'ingredients_highlighted_labeled':label(r'Thành phần(?: chính| nổi bật| nổi trội)?'),
        'ingredients_full_labeled':label(r'(?:Thành phần đầy đủ|Full ingredients|Ingredients)'),
        'target_skin_or_hair_labeled':label(r'(?:Loại da(?: phù hợp| sử dụng)?|Làn da sử dụng|Loại tóc phù hợp|Đối tượng sử dụng)'),
        'usage_labeled':label(r'(?:Hướng dẫn sử dụng|Cách sử dụng|Cách dùng)'),
        'description_text':description,
        'image_paths_raw':[m.get('url') for m in product.get('medias',[]) if m.get('url')],
        'image_urls_from_html':list(dict.fromkeys(u for u in tree.xpath('//img/@src') if any((m.get('url') or '__none__') in u for m in product.get('medias',[])))),
        'variant_count':len(product.get('variants') or []),'is_active':product.get('isActive'),
        'stock_daily_raw':product.get('stockDaily'),'stock_pickup_daily_raw':product.get('stockPickupDaily'),
        'source_url':url,'fetched_at_utc':now(),
    }
    variants=[]
    for v in product.get('variants') or []:
        variants.append({'product_id':row['product_id'],'variant_id':str(v['id']),'sku':v.get('sku'),
                         'barcode_raw':v.get('barCode'),'price_vnd':v.get('price'),
                         'price_before_discount_vnd':v.get('priceBeforeDiscount'),
                         'attribute_values_raw':v.get('attributeValues'),
                         'stock_raw':v.get('stock'),'stock_pickup_raw':v.get('stockPickup'),
                         'is_active':v.get('isActive'),'source_url':url,'fetched_at_utc':row['fetched_at_utc']})
    return {'product':row,'variants':variants,'raw_product':product}

