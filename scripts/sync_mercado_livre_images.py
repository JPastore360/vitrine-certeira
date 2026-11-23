#!/usr/bin/env python3
"""Resolve Mercado Livre affiliate links and refresh the static product-image map."""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / "index.html"
OUTPUT = ROOT / "data" / "mercado-livre-images.json"
USER_AGENT = "Mozilla/5.0 (compatible; VitrineCerteiraImageSync/1.0; GitHub Actions)"

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

def resolve_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.geturl()

def extract_products(source):
    match = re.search(r"const\\s+products\\s*=\\s*\\[(.*?)\\n\\];", source, re.S)
    if not match:
        return []
    products = []
    blocks = re.split(r"\\n\\s*\\{", match.group(1))
    for block in blocks:
        name = re.search(r'(?:name\\s*:\\s*|"name"\\s*:\\s*)"([^"]+)"', block)
        affiliate = re.search(r'(?:affiliateUrl\\s*:\\s*|"affiliateUrl"\\s*:\\s*)"(https?://[^" ]+)"', block)
        tag = re.search(r'(?:tag\\s*:\\s*|"tag"\\s*:\\s*)"([^"]+)"', block)
        if name and affiliate and tag and tag.group(1).upper() == "MERCADO LIVRE":
            products.append({"name": name.group(1).strip(), "url": affiliate.group(1).strip()})
    return products

def ids_from_url(url):
    item_ids = re.findall(r"(MLB\\d{6,})", url, re.I)
    catalog_ids = re.findall(r"(MLBU\\d{6,})", url, re.I)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    for values in query.values():
        for value in values:
            item_ids += re.findall(r"(MLB\\d{6,})", value, re.I)
            catalog_ids += re.findall(r"(MLBU\\d{6,})", value, re.I)
    return list(dict.fromkeys(x.upper() for x in item_ids)), list(dict.fromkeys(x.upper() for x in catalog_ids))

def photo_from(data):
    for picture in data.get("pictures") or []:
        if isinstance(picture, dict):
            for key in ("secure_url", "url"):
                photo = picture.get(key)
                if isinstance(photo, str) and photo.startswith("http"):
                    return photo
    photo = data.get("thumbnail") or data.get("secure_thumbnail")
    if isinstance(photo, str) and photo.startswith("http"):
        return photo.replace("-I.jpg", "-O.jpg")
    return None

def search_by_title(title):
    url = "https://api.mercadolibre.com/sites/MLB/search?q=" + urllib.parse.quote(title) + "&limit=5
    try:
        results = (get_json(url).get("results") or [])
        tokens = {t for t in re.findall(r"[a-z0-9]+", title.lower()) if len(t) > 2}
        for result in results:
            candidate_tokens = {t for t in re.findall(r"[a-z0-9]+", (result.get("title") or "").lower()) if len(t) > 2}
            if tokens and len(tokens & candidate_tokens) / len(tokens) >= 0.35:
                photo = photo_from(result)
                if photo:
                    return photo
    except Exception as exc:
        print(f"Fallback de busca falhou para {title!r}: {exc}")
    return None

def main():
    products = extract_products(HTML_FILE.read_text(encoding="utf-8"))
    image_map = {}
    for product in products:
        affiliate = product["url"]
        try:
            final_url = resolve_url(affiliate)
        except Exception as exc:
            print(f"Não foi possível resolver link {affiliate}: {exc}")
            final_url = affiliate
        item_ids, catalog_ids = ids_from_url(final_url)
        endpoints = ["https://api.mercadolibre.com/items/" + item_id for item_id in item_ids]
        endpoints += ["https://api.mercadolibre.com/products/" + catalog_id for catalog_id in catalog_ids]
        for endpoint in dict.fromkeys(endpoints):
            try:
                photo = photo_from(get_json(endpoint))
                if photo:
                    image_map[affiliate] = photo
                    break
            except Exception as exc:
                print(f"Consulta falhou {endpoint}: {exc}")
        if affiliate not in image_map:
            photo = search_by_title(product["name"])
            if photo:
                image_map[affiliate] = photo
        print(f'{product["name"]}: {"foto encontrada" if affiliate in image_map else "sem foto"}')
        time.sleep(0.25)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(image_map, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(f"Mapa atualizado: {len(image_map)} fotos para {len(products)} produtos Mercado Livre.")

if __name__ == "__main__":
    main()
