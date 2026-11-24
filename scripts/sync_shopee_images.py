#!/usr/bin/env python3
"""Recover images for existing Shopee affiliate products without changing affiliate URLs.

Searches the official Shopee Affiliate GraphQL productOfferV2 endpoint by the
existing catalog title. An image is mapped only when the returned product name
has a strong, unambiguous textual match. Uncertain matches stay without an image.
"""
import hashlib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / "index.html"
IMAGE_MAP_FILE = ROOT / "data" / "shopee-images.json"
REPORT_FILE = ROOT / "data" / "shopee-image-sync-report.json"
ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"
USER_AGENT = "VitrineCerteiraShopeeImageSync/1.0"
MAX_ATTEMPTS = 3
MIN_SCORE = 0.67
MIN_RECALL = 0.62
MIN_COMMON_TOKENS = 3
REQUEST_PAUSE_SECONDS = 0.8

STOP_WORDS = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "com", "para", "por", "e", "ou", "sem", "um", "uma", "uns",
    "umas", "ao", "aos", "tipo", "modelo", "original", "novo", "nova", "kit",
    "unidade", "unidades", "peca", "pecas", "produto", "produtos", "oficial",
    "promocao", "oferta", "frete", "brasil",
}


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def tokens(text):
    return {
        token for token in normalize(text).split()
        if token not in STOP_WORDS and (len(token) > 1 or token.isdigit())
    }


def query_for_title(title):
    # Keep identifying words and model numbers, while avoiding very long API keywords.
    selected = []
    for token in normalize(title).split():
        if token in STOP_WORDS or (len(token) < 2 and not token.isdigit()):
            continue
        if token not in selected:
            selected.append(token)
        if len(selected) >= 12:
            break
    return " ".join(selected)[:100]


def extract_products(html):
    match = re.search(r"const\s+products\s*=\s*\[(.*?)\n\];", html, re.S)
    if not match:
        raise RuntimeError("Não foi possível localizar o array const products em index.html.")
    products = []
    # The catalog uses one flat object per product; each object starts on its own line.
    for block in re.split(r"(?m)^\s*\{", match.group(1))[1:]:
        name = re.search(r'(?:"name"|name)\s*:\s*"([^"]+)"', block)
        affiliate = re.search(r'(?:"affiliateUrl"|affiliateUrl)\s*:\s*"(https://[^"]+)"', block)
        image = re.search(r'(?:"image"|image)\s*:\s*"([^"]*)"', block)
        if not name or not affiliate:
            continue
        url = affiliate.group(1).strip()
        if "s.shopee.com.br/" not in url.lower():
            continue
        if image and image.group(1).strip():
            continue
        products.append({"name": name.group(1).strip(), "affiliateUrl": url})
    # Deduplicate the input while preserving catalog order.
    seen = set()
    unique = []
    for item in products:
        if item["affiliateUrl"] not in seen:
            seen.add(item["affiliateUrl"])
            unique.append(item)
    return unique


def signed_request(app_id, secret, query):
    body = json.dumps({"query": query}, separators=(",", ":"), ensure_ascii=False)
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
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
                if payload.get("errors"):
                    messages = [
                        error.get("message", "Erro GraphQL")
                        for error in payload["errors"]
                    ]
                    raise RuntimeError("Shopee GraphQL: " + " | ".join(messages))
                return payload
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"Shopee HTTP {exc.code}: {details[:500]}") from exc
    raise RuntimeError("A API Shopee não respondeu após novas tentativas.")


def search_products(app_id, secret, keyword):
    query = """{
      productOfferV2(keyword: %s, sortType: 1, page: 1, limit: 5) {
        nodes { productName imageUrl }
        pageInfo { page limit hasNextPage }
      }
    }""" % json.dumps(keyword, ensure_ascii=False)
    payload = signed_request(app_id, secret, query)
    result = ((payload.get("data") or {}).get("productOfferV2") or {})
    return result.get("nodes") or []


def similarity(original, candidate):
    original_tokens = tokens(original)
    candidate_tokens = tokens(candidate)
    common = original_tokens & candidate_tokens
    if not original_tokens or not candidate_tokens:
        return 0.0, 0.0, len(common)
    recall = len(common) / len(original_tokens)
    precision = len(common) / len(candidate_tokens)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    sequence = SequenceMatcher(None, normalize(original), normalize(candidate)).ratio()
    return (0.75 * f1 + 0.25 * sequence), recall, len(common)


def main():
    app_id = os.environ.get("SHOPEE_APP_ID", "").strip()
    secret = os.environ.get("SHOPEE_APP_SECRET", "").strip()
    if not app_id or not secret:
        raise SystemExit("Faltam SHOPEE_APP_ID ou SHOPEE_APP_SECRET nos GitHub Secrets.")

    catalog = extract_products(HTML_FILE.read_text(encoding="utf-8"))
    image_map = load_json(IMAGE_MAP_FILE, {})
    report = load_json(REPORT_FILE, {"attempts": {}, "results": {}})
    report.setdefault("attempts", {})
    report.setdefault("results", {})

    pending = [
        item for item in catalog
        if item["affiliateUrl"] not in image_map
        and report["attempts"].get(item["affiliateUrl"], 0) < MAX_ATTEMPTS
    ]

    print(f"Produtos Shopee antigos sem imagem: {len(catalog)}")
    print(f"Imagens já recuperadas anteriormente: {len(image_map)}")
    print(f"Produtos que serão pesquisados nesta execução: {len(pending)}")

    matched = 0
    no_match = 0
    for index, item in enumerate(pending, 1):
        affiliate_url = item["affiliateUrl"]
        title = item["name"]
        keyword = query_for_title(title)
        print(f"[{index}/{len(pending)}] Pesquisando: {title}")
        try:
            nodes = search_products(app_id, secret, keyword)
            ranked = []
            for node in nodes:
                candidate_name = node.get("productName") or ""
                image_url = node.get("imageUrl") or ""
                if not candidate_name or not image_url.startswith("https://"):
                    continue
                if "shopee.com.br" not in image_url.lower():
                    continue
                score, recall, common = similarity(title, candidate_name)
                ranked.append({
                    "name": candidate_name,
                    "image": image_url,
                    "score": round(score, 4),
                    "recall": round(recall, 4),
                    "commonTokens": common,
                })
            ranked.sort(key=lambda result: result["score"], reverse=True)
            best = ranked[0] if ranked else None
            second = ranked[1] if len(ranked) > 1 else None
            margin_ok = not second or (best["score"] - second["score"] >= 0.04)
            accepted = bool(
                best
                and best["score"] >= MIN_SCORE
                and best["recall"] >= MIN_RECALL
                and best["commonTokens"] >= MIN_COMMON_TOKENS
                and margin_ok
            )
            report["attempts"][affiliate_url] = report["attempts"].get(affiliate_url, 0) + 1
            if accepted:
                image_map[affiliate_url] = best["image"]
                report["results"][affiliate_url] = {
                    "status": "matched",
                    "originalName": title,
                    "matchedName": best["name"],
                    "score": best["score"],
                    "image": best["image"],
                }
                matched += 1
                print(f"  FOTO ENCONTRADA (score {best['score']:.2f}): {best['name']}")
            else:
                report["results"][affiliate_url] = {
                    "status": "needs_review" if best else "not_found",
                    "originalName": title,
                    "keyword": keyword,
                    "bestCandidate": best,
                    "secondCandidate": second,
                }
                no_match += 1
                print("  Sem correspondência segura; imagem não será atribuída.")
        except Exception as exc:
            report["results"][affiliate_url] = {
                "status": "api_error",
                "originalName": title,
                "keyword": keyword,
                "error": str(exc)[:500],
            }
            print(f"  ERRO nesta pesquisa: {exc}")
            # Do not continue a hundred requests if authentication/schema failed globally.
            if "HTTP 401" in str(exc) or "HTTP 403" in str(exc) or "GraphQL:" in str(exc):
                raise
        time.sleep(REQUEST_PAUSE_SECONDS)

    IMAGE_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_MAP_FILE.write_text(
        json.dumps(image_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report["summary"] = {
        "catalogMissingAtRun": len(catalog),
        "alreadyRecovered": len(image_map),
        "searchedThisRun": len(pending),
        "matchedThisRun": matched,
        "notMatchedThisRun": no_match,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print("========================================")
    print(f"Fotos recuperadas nesta execução: {matched}")
    print(f"Sem correspondência segura: {no_match}")
    print(f"Total de imagens no mapa Shopee: {len(image_map)}")
    print("Links de afiliado originais não foram alterados.")
    if pending and matched == 0 and no_match == 0:
        raise SystemExit("Nenhuma busca foi concluída.")
    

if __name__ == "__main__":
    main()
