#!/usr/bin/env python3
"""Daily Shopee bestseller collector for Vitrine Certeira.

Collects by Shopee Affiliate Open API productOfferV2 sorted by sales,
validates affiliate link/image/price/sales/rating/commission, deduplicates
against the existing HTML catalog and feed, then appends at most 15 products.
"""
import difflib
import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FEED_FILE = ROOT / "data" / "shopee-products.json"
REPORT_FILE = ROOT / "data" / "shopee-bestsellers-report.json"
HTML_FILE = ROOT / "index.html"
ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
USER_AGENT = "VitrineCerteiraBestsellers/1.0"

DAILY_TARGET = 15
RESULTS_PER_KEYWORD = 50
MIN_SALES = 1
MIN_RATING = 4.5
MIN_COMMISSION = 0.0001
REQUEST_PAUSE = 0.8

# Category discovery terms cover the current Vitrine Certeira sections.
SEARCHES = [
    ("tech", "Tecnologia", "fone bluetooth"),
    ("tech", "Tecnologia", "celular smartphone"),
    ("casa", "Casa & Cozinha", "utensilios cozinha"),
    ("casa", "Casa & Cozinha", "liquidificador"),
    ("tools", "Ferramentas", "ferramentas eletricas"),
    ("games", "Games", "controle gamer"),
    ("perfume", "Perfumes", "perfume feminino"),
    ("auto", "Automotivo", "acessorios automotivos"),
    ("agro", "Agro", "jardinagem ferramentas"),
    ("util", "Utilidades", "utilidades domesticas"),
]

STOP_WORDS = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "com", "para", "por", "e", "ou", "um", "uma", "kit",
    "original", "novo", "nova", "oficial", "oferta", "promocao",
}


def set_output(name, value):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def local_today():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def title_tokens(value):
    return {
        item for item in normalize(value).split()
        if item not in STOP_WORDS and len(item) > 1
    }


def is_duplicate_name(candidate, existing_names):
    candidate_tokens = title_tokens(candidate)
    for name in existing_names:
        existing_tokens = title_tokens(name)
        if not candidate_tokens or not existing_tokens:
            continue
        overlap = len(candidate_tokens & existing_tokens) / max(
            1, min(len(candidate_tokens), len(existing_tokens))
        )
        sequence = difflib.SequenceMatcher(
            None, normalize(candidate), normalize(name)
        ).ratio()
        if overlap >= 0.88 or sequence >= 0.90:
            return True
    return False


def to_number(value):
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return 0.0


def format_brl(value):
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    return "R$ " + f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def signed_graphql(app_id, secret, query):
    body = json.dumps({"query": query}, separators=(",", ":"), ensure_ascii=False)
    last_error = None
    for attempt in range(4):
        timestamp = str(int(time.time()))
        signature = hashlib.sha256(
            (app_id + timestamp + body + secret).encode("utf-8")
        ).hexdigest()
        authorization = (
            f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={signature}"
        )
        request = urllib.request.Request(
            ENDPOINT,
            data=body.encode("utf-8"),
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if payload.get("errors"):
                messages = [
                    item.get("message", "Erro GraphQL")
                    for item in payload["errors"]
                ]
                last_error = " | ".join(messages)
                retryable = any(
                    marker in last_error.lower()
                    for marker in ("system error", "rate limit", "temporarily")
                )
                if retryable and attempt < 3:
                    wait = 2 ** attempt
                    print(f"  Erro temporário da Shopee; nova tentativa em {wait}s.")
                    time.sleep(wait)
                    continue
                raise RuntimeError("Shopee GraphQL: " + last_error)
            return payload
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {body_text[:400]}"
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                wait = 2 ** attempt
                print(f"  HTTP {exc.code}; nova tentativa em {wait}s.")
                time.sleep(wait)
                continue
            raise RuntimeError(last_error) from exc
        except urllib.error.URLError as exc:
            last_error = str(exc.reason)
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Falha de conexão Shopee: {last_error}") from exc
    raise RuntimeError(last_error or "Falha desconhecida ao consultar Shopee.")


def fetch_keyword(app_id, secret, keyword):
    query = """{
      productOfferV2(
        keyword: %s,
        sortType: 2,
        page: 1,
        limit: %d
      ) {
        nodes {
          itemId
          productName
          productLink
          offerLink
          imageUrl
          priceMin
          priceMax
          priceDiscountRate
          sales
          ratingStar
          commissionRate
          shopId
          shopName
        }
        pageInfo { page limit hasNextPage }
      }
    }""" % (json.dumps(keyword, ensure_ascii=False), RESULTS_PER_KEYWORD)
    response = signed_graphql(app_id, secret, query)
    result = ((response.get("data") or {}).get("productOfferV2") or {})
    return result.get("nodes") or []


def price_for(item):
    low = to_number(item.get("priceMin"))
    high = to_number(item.get("priceMax"))
    if low <= 0:
        return ""
    if high > low + 0.009:
        return f"{format_brl(low)} a {format_brl(high)}"
    return format_brl(low)


def affiliate_link_is_valid(value):
    return bool(re.match(r"^https://s\.shopee\.com\.br/[A-Za-z0-9]+$", str(value or ""), re.I))


def image_is_valid(value):
    return bool(re.match(r"^https://cf\.shopee\.com\.br/file/[A-Za-z0-9-]+$", str(value or ""), re.I))


def extract_existing_html_products():
    html = HTML_FILE.read_text(encoding="utf-8")
    match = re.search(r"const\s+products\s*=\s*\[(.*?)\n\];", html, re.S)
    if not match:
        raise RuntimeError("Não encontrei o catálogo principal em index.html.")
    names, links, ids = [], set(), set()
    for block in re.split(r"\n\s*\{", match.group(1))[1:]:
        name = re.search(r'name\s*:\s*"([^"]+)"', block)
        link = re.search(r'affiliateUrl\s*:\s*"(https://[^"]+)"', block)
        item = re.search(r'(?:itemId|productId)\s*:\s*"?(\d+)"?', block)
        if name:
            names.append(name.group(1))
        if link:
            links.add(link.group(1))
        if item:
            ids.add(str(item.group(1)))
    return names, links, ids


def main():
    app_id = os.environ.get("SHOPEE_APP_ID", "").strip()
    secret = os.environ.get("SHOPEE_APP_SECRET", "").strip()
    if not app_id or not secret:
        raise SystemExit("Faltam SHOPEE_APP_ID ou SHOPEE_APP_SECRET nos GitHub Secrets.")

    feed = load_json(FEED_FILE, {
        "source": "Shopee Affiliate API - productOfferV2",
        "country": "BR",
        "products": [],
        "dailyBatches": [],
    })
    feed.setdefault("products", [])
    feed.setdefault("dailyBatches", [])
    report = {
        "date": local_today(),
        "target": DAILY_TARGET,
        "added": 0,
        "searches": [],
        "selected": [],
        "rejected": {},
    }

    today = local_today()
    if today in feed["dailyBatches"]:
        print(f"A meta diária de {today} já foi processada. Nada será adicionado em duplicidade.")
        set_output("products_added", "0")
        set_output("feed_changed", "false")
        return

    existing_names, existing_links, existing_ids = extract_existing_html_products()
    feed_names = [p.get("name", "") for p in feed["products"]]
    feed_links = {p.get("affiliateUrl") for p in feed["products"] if p.get("affiliateUrl")}
    feed_ids = {str(p.get("itemId") or "") for p in feed["products"] if p.get("itemId")}
    all_names = existing_names + feed_names
    all_links = existing_links | feed_links
    all_ids = existing_ids | feed_ids

    candidates = {}
    search_errors = 0
    for category, category_name, keyword in SEARCHES:
        print(f"Buscando mais vendidos: {keyword} (ordenação por quantidade vendida)")
        try:
            nodes = fetch_keyword(app_id, secret, keyword)
            report["searches"].append({
                "keyword": keyword,
                "category": category_name,
                "returned": len(nodes),
                "sort": "sales_desc",
                "status": "ok",
            })
            for item in nodes:
                item_id = str(item.get("itemId") or "")
                name = str(item.get("productName") or "").strip()
                link = str(item.get("offerLink") or "").strip()
                image = str(item.get("imageUrl") or "").strip()
                price = price_for(item)
                sales = int(to_number(item.get("sales")))
                rating = to_number(item.get("ratingStar"))
                commission = to_number(item.get("commissionRate"))

                if not name or not item_id or not affiliate_link_is_valid(link):
                    report["rejected"]["invalid_affiliate_or_name"] = report["rejected"].get("invalid_affiliate_or_name", 0) + 1
                    continue
                if not image_is_valid(image) or not price:
                    report["rejected"]["missing_image_or_price"] = report["rejected"].get("missing_image_or_price", 0) + 1
                    continue
                if sales < MIN_SALES:
                    report["rejected"]["not_enough_sales"] = report["rejected"].get("not_enough_sales", 0) + 1
                    continue
                if rating < MIN_RATING:
                    report["rejected"]["rating_below_4_5_or_missing"] = report["rejected"].get("rating_below_4_5_or_missing", 0) + 1
                    continue
                if commission < MIN_COMMISSION:
                    report["rejected"]["no_affiliate_commission"] = report["rejected"].get("no_affiliate_commission", 0) + 1
                    continue
                if link in all_links or item_id in all_ids or is_duplicate_name(name, all_names):
                    report["rejected"]["duplicate"] = report["rejected"].get("duplicate", 0) + 1
                    continue

                candidate = {
                    "itemId": item_id,
                    "name": name,
                    "productLink": str(item.get("productLink") or ""),
                    "affiliateUrl": link,
                    "image": image,
                    "price": price,
                    "sales": sales,
                    "ratingStar": rating,
                    "commissionRate": commission,
                    "shopId": str(item.get("shopId") or ""),
                    "shopName": str(item.get("shopName") or ""),
                    "category": category,
                    "categoryName": category_name,
                    "keyword": keyword,
                }
                current = candidates.get(item_id)
                if current is None or candidate["sales"] > current["sales"]:
                    candidates[item_id] = candidate
        except Exception as exc:
            search_errors += 1
            report["searches"].append({
                "keyword": keyword,
                "category": category_name,
                "status": "error",
                "error": str(exc)[:400],
            })
            print(f"  Erro nesta busca; as outras categorias continuarão: {exc}")
            if "HTTP 401" in str(exc) or "HTTP 403" in str(exc) or "signature" in str(exc).lower():
                raise
        time.sleep(REQUEST_PAUSE)

    ranked = sorted(
        candidates.values(),
        key=lambda x: (x["sales"], x["ratingStar"], x["commissionRate"]),
        reverse=True,
    )
    selected = ranked[:DAILY_TARGET]
    for candidate in selected:
        new_product = {
            "id": f"shopee-{candidate['itemId']}",
            "itemId": candidate["itemId"],
            "store": "Shopee",
            "name": candidate["name"],
            "category": candidate["category"],
            "categoryName": candidate["categoryName"],
            "description": (
                f"Mais vendido na Shopee: {candidate['sales']} vendas registradas. "
                f"Avaliação {candidate['ratingStar']:.1f}/5 na loja {candidate['shopName']}."
            ),
            "price": candidate["price"],
            "image": candidate["image"],
            "affiliateUrl": candidate["affiliateUrl"],
            "tag": "SHOPEE • MAIS VENDIDO",
            "icon": "🏆",
            "sales": candidate["sales"],
            "ratingStar": candidate["ratingStar"],
            "commissionRate": candidate["commissionRate"],
            "shopName": candidate["shopName"],
            "productLink": candidate["productLink"],
            "addedAt": today,
        }
        feed["products"].append(new_product)
        report["selected"].append({
            "itemId": candidate["itemId"],
            "name": candidate["name"],
            "sales": candidate["sales"],
            "ratingStar": candidate["ratingStar"],
            "commissionRate": candidate["commissionRate"],
            "category": candidate["categoryName"],
        })
        all_names.append(candidate["name"])
        all_links.add(candidate["affiliateUrl"])
        all_ids.add(candidate["itemId"])

    report["added"] = len(selected)
    report["searchErrors"] = search_errors
    report["candidatePool"] = len(ranked)
    report["minimums"] = {
        "sales": MIN_SALES,
        "rating": MIN_RATING,
        "commissionRate": MIN_COMMISSION,
        "requiredImage": True,
        "requiredAffiliateLink": True,
    }
    report["updatedAt"] = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()

    # Mark the day only if enough searches succeeded to make a meaningful decision.
    successful_searches = sum(1 for item in report["searches"] if item.get("status") == "ok")
    if successful_searches >= 5:
        feed["dailyBatches"].append(today)
        feed["dailyBatches"] = feed["dailyBatches"][-90:]
        feed["lastValidatedAt"] = report["updatedAt"]
        feed["lastDailyAdded"] = len(selected)
        feed["selectionRule"] = (
            "Top 15 by sales (sortType=2), rating >= 4.5, positive commission, "
            "valid affiliate link, valid image, valid price and no duplicates."
        )
    else:
        print("Menos de cinco categorias responderam. A data não será marcada como processada.")

    FEED_FILE.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    feed_changed = bool(selected)
    set_output("products_added", str(len(selected)))
    set_output("feed_changed", "true" if feed_changed else "false")

    print("========================================")
    print(f"Produtos novos adicionados hoje: {len(selected)} de {DAILY_TARGET}")
    print(f"Pool aprovado antes do corte diário: {len(ranked)}")
    print(f"Buscas com erro: {search_errors}")
    print("Critérios: vendidos, avaliação mínima 4,5, comissão positiva, foto, preço e link afiliado.")
    for index, item in enumerate(selected, 1):
        print(f"{index:02d}. {item['name']} | vendas={item['sales']} | nota={item['ratingStar']:.1f} | {item['price']}")
    if len(selected) < DAILY_TARGET:
        print("Atenção: não houve 15 produtos que passassem em todos os critérios. Não foram incluídos produtos fracos para completar a meta.")


if __name__ == "__main__":
    main()
