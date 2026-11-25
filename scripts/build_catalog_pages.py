#!/usr/bin/env python3
"""Build static, crawlable product grids and category landing pages for Vitrine Certeira."""
from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
FEED_FILE = ROOT / "data" / "shopee-products.json"
HOME_FILE = ROOT / "index.html"
SITEMAP_FILE = ROOT / "sitemap.xml"
BASE_URL = "https://vitrinecerteira.com.br"

CATEGORY_META = {
    "tech": {
        "slug": "tecnologia", "name": "Tecnologia", "emoji": "📱",
        "title": "Achados de tecnologia e acessórios | Vitrine Certeira",
        "description": "Seleção de acessórios, áudio, carregadores e gadgets. Compare compatibilidade, especificações, avaliações e preços antes de escolher.",
        "intro": "Reunimos acessórios e dispositivos de tecnologia encontrados na curadoria da Vitrine Certeira. A lista é atualizada quando novos itens passam pelos critérios de imagem, preço, link de afiliado e avaliação. Antes de comprar, confira a compatibilidade com seu aparelho e as especificações diretamente na loja.",
        "tips": ["Confirme compatibilidade com o modelo e a versão do seu aparelho.", "Compare conexões, potência, capacidade e recursos que você realmente vai usar.", "Leia avaliações recentes e confira a reputação do vendedor.", "Verifique garantia, prazo, frete e política de devolução na loja."],
        "guide": "tecnologia.html",
    },
    "casa": {
        "slug": "casa-cozinha", "name": "Casa & Cozinha", "emoji": "🏠",
        "title": "Achados para casa e cozinha | Vitrine Certeira",
        "description": "Produtos para cozinha, organização e rotina doméstica. Compare medidas, materiais, facilidade de limpeza, voltagem e custo-benefício.",
        "intro": "Esta seleção reúne utilidades para cozinha e casa encontradas na curadoria da Vitrine Certeira. Os itens entram no catálogo quando apresentam informações básicas, imagem e link de afiliado válidos. Compare medidas e materiais com o espaço disponível e confira as condições atuais na loja.",
        "tips": ["Meça o espaço antes de escolher organizadores e utensílios.", "Confira material, capacidade, dimensões e facilidade de limpeza.", "Em aparelhos elétricos, confirme a voltagem e a potência.", "Compare o preço final com frete e condições de entrega."],
        "guide": "casa-utilidades.html",
    },
    "tools": {
        "slug": "ferramentas", "name": "Ferramentas", "emoji": "🧰",
        "title": "Achados de ferramentas e equipamentos | Vitrine Certeira",
        "description": "Ferramentas manuais e elétricas para manutenção e pequenos reparos. Compare potência, encaixes, acessórios e segurança.",
        "intro": "Nesta página você encontra ferramentas e acessórios selecionados para tarefas domésticas, manutenção e uso profissional leve. A ferramenta correta depende do serviço, da frequência de uso e dos materiais envolvidos; confira sempre as especificações e recomendações do fabricante.",
        "tips": ["Defina a tarefa antes de escolher o tipo e a potência da ferramenta.", "Confira encaixes, medidas, acessórios e disponibilidade de peças.", "Verifique tensão elétrica, bateria e compatibilidade dos componentes.", "Use os equipamentos de proteção indicados e siga o manual do fabricante."],
        "guide": "ferramentas.html",
    },
    "auto": {
        "slug": "automotivo", "name": "Automotivo", "emoji": "🚘",
        "title": "Achados automotivos para carro e moto | Vitrine Certeira",
        "description": "Acessórios e itens automotivos para carro e moto. Confira compatibilidade, instalação, segurança, materiais e custo-benefício.",
        "intro": "A curadoria automotiva reúne acessórios e utilidades para carro e moto. Antes de escolher, confira se o produto serve para o modelo, ano e versão do veículo. Itens relacionados à segurança e à instalação devem seguir as especificações do fabricante e as regras aplicáveis.",
        "tips": ["Confirme modelo, ano, versão e medidas de compatibilidade.", "Verifique se a instalação exige profissional especializado.", "Em itens elétricos, confira tensão, conectores e consumo.", "Não substitua peças de segurança por acessórios sem especificação adequada."],
        "guide": "automotivo.html",
    },
    "agro": {
        "slug": "agro-campo", "name": "Agro & Campo", "emoji": "🌱",
        "title": "Achados para agro, sítio e vida rural | Vitrine Certeira",
        "description": "Ferramentas, acessórios e utilidades para sítio e fazenda. Compare capacidade, resistência, manutenção e adequação ao trabalho.",
        "intro": "Esta seleção reúne itens úteis para o campo, jardinagem e rotina rural. Poeira, umidade, exposição ao sol, frequência de uso e disponibilidade de peças influenciam a durabilidade. Confira as especificações e a assistência disponível antes de comprar.",
        "tips": ["Considere poeira, umidade, sol e intensidade de uso no ambiente.", "Compare capacidade, autonomia, dimensões e materiais.", "Confira bateria, peças de reposição e facilidade de manutenção.", "Para produtos de aplicação, siga o rótulo e as orientações técnicas do fabricante."],
        "guide": "guia-produtos-rurais.html",
    },
    "perfume": {
        "slug": "perfumes-cuidados", "name": "Perfumes & Cuidados", "emoji": "🧴",
        "title": "Achados de perfumes e cuidados pessoais | Vitrine Certeira",
        "description": "Fragrâncias e produtos de cuidado pessoal. Compare volume, concentração, perfil olfativo, vendedor e condições da oferta.",
        "intro": "A seleção de perfumes e cuidados pessoais ajuda a descobrir opções e comparar apresentações. A percepção de uma fragrância varia de pessoa para pessoa; consulte a descrição do fabricante, confira o volume e dê preferência a vendedores com procedência e informações claras.",
        "tips": ["Observe família olfativa, concentração e descrição do fabricante.", "Compare volume e preço por mililitro.", "Confira procedência, lacre, vendedor e política de devolução.", "Considere que a fixação percebida varia conforme pele, clima e uso."],
        "guide": "perfumes.html",
    },
    "games": {
        "slug": "games", "name": "Games & Acessórios", "emoji": "🎮",
        "title": "Achados gamer, controles e acessórios | Vitrine Certeira",
        "description": "Controles, periféricos e acessórios gamer. Confira plataforma compatível, conexão, ergonomia e especificações.",
        "intro": "Aqui reunimos acessórios para jogos e equipamentos relacionados a PC, consoles e dispositivos móveis. A compatibilidade é essencial: confirme a plataforma, os sistemas suportados e os recursos que funcionam em cada aparelho antes de fechar o pedido.",
        "tips": ["Confirme compatibilidade com PC, PlayStation, Xbox, Switch ou celular.", "Compare conexão com fio, Bluetooth, receptor e latência anunciada.", "Considere ergonomia, peso, autonomia e conforto.", "Confira garantia e política de troca para periféricos."],
        "guide": "games.html",
    },
    "util": {
        "slug": "utilidades", "name": "Utilidades", "emoji": "✨",
        "title": "Achados e utilidades do dia a dia | Vitrine Certeira",
        "description": "Utilidades para a rotina e para casa. Compare função, tamanho, material e avaliações antes de escolher.",
        "intro": "Itens práticos podem facilitar tarefas do cotidiano, mas a escolha depende de medidas, material e frequência de uso. Confira os detalhes do anúncio e compare opções antes de comprar.",
        "tips": ["Confira dimensões e material.", "Compare a função anunciada com sua necessidade real.", "Leia avaliações e verifique fotos de compradores.", "Considere frete, prazo e facilidade de devolução."],
        "guide": "casa-utilidades.html",
    },
}

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def valid_https(value: object) -> bool:
    try:
        parsed = urlparse(str(value or "").strip())
        return parsed.scheme == "https" and bool(parsed.netloc)
    except Exception:
        return False


def normal_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def read_static_products(home: str) -> list[dict]:
    start = home.find("const products = [")
    if start < 0:
        return []
    start = home.find("[", start)
    end = home.find("\n];", start)
    if end < 0:
        return []
    array_text = home[start + 1:end]
    products = []
    for match in re.finditer(r"\{([^{}]*)\}", array_text, re.S):
        block = match.group(1)
        item = {}
        for key in ("name", "category", "categoryName", "description", "price",
                    "image", "affiliateUrl", "tag", "icon"):
            field = re.search(
                r"""["']?""" + re.escape(key) + r"""["']?\s*:\s*("(?:\\.|[^"\\])*")""",
                block,
            )
            if field:
                try:
                    item[key] = json.loads(field.group(1))
                except json.JSONDecodeError:
                    pass
        if item.get("name") and valid_https(item.get("image")) and valid_https(item.get("affiliateUrl")):
            item.setdefault("store", "Parceiro")
            products.append(item)
    return products


def prepare_products(feed_products: list[dict], static_products: list[dict]) -> list[dict]:
    output = []
    seen_links = set()
    seen_ids = set()
    seen_names = []
    # Prefer official current feed data to older inline listings.
    for source in (feed_products, static_products):
        for raw in source:
            item = dict(raw)
            name = str(item.get("name") or "").strip()
            image = str(item.get("image") or "").strip()
            link = str(item.get("affiliateUrl") or "").strip()
            if not name or not valid_https(image) or not valid_https(link):
                continue
            link_key = link.rstrip("/")
            item_id = str(item.get("itemId") or "")
            normalized = normal_name(name)
            if link_key in seen_links or (item_id and item_id in seen_ids):
                continue
            # Remove only near-identical titles, not ordinary products in the same family.
            if any(SequenceMatcher(None, normalized, prior).ratio() >= 0.97 for prior in seen_names):
                continue
            item["name"] = name
            item["image"] = image
            item["affiliateUrl"] = link
            item["category"] = str(item.get("category") or "util")
            item["categoryName"] = str(item.get("categoryName") or CATEGORY_META.get(item["category"], {}).get("name", "Achados"))
            item["description"] = str(item.get("description") or "Consulte as especificações e condições diretamente na loja.")
            item["price"] = str(item.get("price") or "Consulte na loja")
            item["tag"] = str(item.get("tag") or "ACHADO SELECIONADO")
            output.append(item)
            seen_links.add(link_key)
            if item_id:
                seen_ids.add(item_id)
            seen_names.append(normalized)
    return output


def card_html(p: dict, compact: bool = False) -> str:
    rating = float(p.get("ratingStar") or 0)
    sales = int(float(p.get("sales") or 0))
    proof = ""
    if rating > 0 or sales > 0:
        parts = []
        if rating > 0:
            parts.append(f'<span class="proof-rating">★ {rating:.1f}/5</span>')
        if sales > 0:
            parts.append(f'<span>{sales:,} vendas</span>'.replace(",", "."))
        proof = '<div class="card-proof">' + "".join(parts) + "</div>"
    return f"""
<article class="product-card">
  <a class="product-photo" href="{esc(p['affiliateUrl'])}" target="_blank" rel="nofollow sponsored noopener" aria-label="Ver {esc(p['name'])} na loja">
    <img src="{esc(p['image'])}" alt="{esc(p['name'])}" loading="lazy" decoding="async">
    <span class="product-tag">{esc(p.get('tag') or 'ACHADO SELECIONADO')}</span>
  </a>
  <div class="product-body">
    <p class="product-category">{esc(p.get('categoryName'))}</p>
    <h2>{esc(p['name'])}</h2>
    <p class="product-description">{esc(p.get('description'))}</p>
    {proof}
    <p class="product-price">{esc(p.get('price'))}</p>
    <a class="product-button" href="{esc(p['affiliateUrl'])}" target="_blank" rel="nofollow sponsored noopener">Conferir oferta na loja ↗</a>
  </div>
</article>"""


def category_page(key: str, meta: dict, products: list[dict], updated: str) -> str:
    canonical = f"{BASE_URL}/achados/{meta['slug']}/"
    product_cards = "\n".join(card_html(p, compact=True) for p in products)
    tips = "\n".join(f"<li>{esc(tip)}</li>" for tip in meta["tips"])
    guide_url = f"/{meta['guide']}"
    related = []
    for other_key, other_meta in CATEGORY_META.items():
        if other_key != key and other_key in products_by_category:
            related.append(f'<a href="/achados/{other_meta["slug"]}/">{esc(other_meta["name"])}</a>')
    related_html = " · ".join(related[:6])
    structured = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": meta["title"],
        "description": meta["description"],
        "url": canonical,
        "dateModified": updated,
        "isPartOf": {"@type": "WebSite", "name": "Vitrine Certeira", "url": BASE_URL + "/"},
        "breadcrumb": {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Início", "item": BASE_URL + "/"},
                {"@type": "ListItem", "position": 2, "name": "Categorias", "item": BASE_URL + "/categorias.html"},
                {"@type": "ListItem", "position": 3, "name": meta["name"], "item": canonical},
            ],
        },
    }
    structured_json = json.dumps(structured, ensure_ascii=False).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta name="description" content="{esc(meta['description'])}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Vitrine Certeira">
<meta property="og:title" content="{esc(meta['title'])}">
<meta property="og:description" content="{esc(meta['description'])}">
<meta property="og:url" content="{esc(canonical)}">
<title>{esc(meta['title'])}</title>
<script type="application/ld+json">{structured_json}</script>
<style>
:root{{--bg:#0d0d0f;--panel:#19191d;--text:#f5f5f6;--muted:#b8b8c0;--accent:#ff921f;--border:#303037}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 Inter,system-ui,-apple-system,"Segoe UI",Arial,sans-serif}}
a{{color:inherit;text-decoration:none}}.wrap{{width:min(1180px,100% - 36px);margin:auto}}
header{{border-bottom:1px solid var(--border);background:#101012}}.nav{{min-height:66px;display:flex;align-items:center;justify-content:space-between;gap:14px}}.brand{{font-weight:900;letter-spacing:.4px}}.brand b{{color:var(--accent)}}.navlinks{{display:flex;gap:18px;flex-wrap:wrap;color:#ddd;font-size:14px}}.navlinks a:hover,.breadcrumbs a:hover{{color:var(--accent)}}
.breadcrumbs{{padding:18px 0;color:var(--muted);font-size:13px}}.hero{{padding:20px 0 30px;max-width:850px}}.eyebrow{{color:var(--accent);font-size:12px;font-weight:800;letter-spacing:1.4px}}h1{{font-size:clamp(34px,5vw,54px);line-height:1.08;letter-spacing:-1.5px;margin:12px 0}}.intro{{color:var(--muted);font-size:17px;max-width:780px}}
.tips{{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:22px;margin:12px 0 34px}}.tips h2{{margin:0 0 10px;font-size:20px}}.tips ul{{margin:0;padding-left:22px;color:#d5d5da}}.tips li{{margin:7px 0}}
.countline{{display:flex;justify-content:space-between;gap:12px;align-items:end;margin:24px 0 14px}}.countline h2{{margin:0;font-size:25px}}.countline p{{margin:0;color:var(--muted);font-size:13px}}
.products{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}.product-card{{background:var(--panel);border:1px solid var(--border);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;min-width:0}}.product-photo{{height:220px;background:#fff;position:relative;display:grid;place-items:center;padding:12px}}.product-photo img{{width:100%;height:100%;object-fit:contain}}.product-tag{{position:absolute;left:10px;top:10px;border-radius:30px;background:#21170e;color:#ffc17d;padding:5px 9px;font-size:10px;font-weight:800}}.product-body{{padding:15px;display:flex;flex-direction:column;flex:1}}.product-category{{color:var(--accent);font-size:11px;font-weight:800;text-transform:uppercase;margin:0 0 5px}}.product-body h2{{font-size:16px;line-height:1.35;margin:0 0 8px}}.product-description{{color:var(--muted);font-size:13px;margin:0 0 8px}}.card-proof{{display:flex;gap:7px;flex-wrap:wrap;margin:2px 0 8px}}.card-proof span{{font-size:11px;color:#ccc;background:#25252a;padding:4px 7px;border-radius:20px}}.proof-rating{{color:#ffd18b!important}}.product-price{{font-size:17px;font-weight:850;margin:auto 0 12px;padding-top:8px}}.product-button{{display:block;text-align:center;padding:11px;background:var(--accent);color:#171717;font-weight:850;border-radius:10px;font-size:13px}}
.related{{margin:36px 0;padding:20px;border-top:1px solid var(--border);color:var(--muted)}}.related a{{color:#ffb45c;text-decoration:underline;margin-right:9px}}.disclosure{{color:#92929a;font-size:12px;border-top:1px solid var(--border);padding:22px 0;margin-top:30px}}
@media(max-width:820px){{.products{{grid-template-columns:repeat(2,minmax(0,1fr))}}.product-photo{{height:190px}}}}
@media(max-width:500px){{.wrap{{width:min(100% - 24px,1180px)}}.nav{{align-items:flex-start;flex-direction:column;padding:13px 0}}.navlinks{{gap:12px;font-size:13px}}.products{{gap:10px}}.product-photo{{height:145px;padding:7px}}.product-body{{padding:11px}}.product-body h2{{font-size:14px}}.product-description{{font-size:12px}}.product-price{{font-size:15px}}.product-button{{font-size:11px;padding:9px}}.countline{{align-items:flex-start;flex-direction:column}}}}
</style>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-ZRZ9ZCZJEH"></script>
<script>
window.dataLayer=window.dataLayer||[];
function gtag(){{dataLayer.push(arguments);}}
gtag('js',new Date());
gtag('config','G-ZRZ9ZCZJEH');
document.addEventListener('click',function(event){{
  const link=event.target.closest('a[rel~="sponsored"]');
  if(!link || typeof gtag!=='function')return;
  const card=link.closest('.product-card,.card');
  const title=card?.querySelector('h2,h3')?.textContent?.trim() || link.getAttribute('aria-label') || '';
  const category=card?.querySelector('.product-category,.catlabel')?.textContent?.trim() || '';
  gtag('event','affiliate_click',{{ 
    product_name:title,
    product_category:category,
    link_url:link.href,
    page_path:location.pathname,
    transport_type:'beacon'
  }});
}});
</script>
</head>
<body>
<header><div class="wrap nav"><a class="brand" href="/">VITRINE <b>CERTEIRA</b></a><nav class="navlinks"><a href="/">Início</a><a href="/categorias.html">Categorias</a><a href="/guia-compra.html">Guias de compra</a><a href="/#achados">Todas as ofertas</a></nav></div></header>
<main class="wrap">
<nav class="breadcrumbs" aria-label="Navegação estrutural"><a href="/">Início</a> › <a href="/categorias.html">Categorias</a> › {esc(meta['name'])}</nav>
<section class="hero"><span class="eyebrow">{meta['emoji']} SELEÇÃO DE PRODUTOS</span><h1>{esc(meta['name'])}: ofertas e produtos selecionados</h1><p class="intro">{esc(meta['intro'])}</p></section>
<section class="tips"><h2>Como escolher melhor nesta categoria</h2><ul>{tips}</ul><p>Consulte sempre a descrição completa, o vendedor, o preço final, o frete e as condições atualizadas na loja parceira.</p><a href="{guide_url}" style="color:#ffb45c;text-decoration:underline">Leia também nosso guia de compra desta categoria →</a></section>
<section><div class="countline"><h2>Produtos disponíveis</h2><p>{len(products)} itens com imagem e link de oferta</p></div><div class="products">{product_cards}</div></section>
<nav class="related" aria-label="Mais categorias"><strong>Explore outras categorias:</strong> {related_html}</nav>
<p class="disclosure">Alguns links desta página são links de afiliado. A Vitrine Certeira pode receber uma comissão se você comprar por eles, sem custo adicional para você. Os produtos são vendidos e entregues pelas lojas parceiras; preços, estoque, frete e condições podem mudar.</p>
</main>
</body>
</html>
"""


def main() -> None:
    feed = json.loads(FEED_FILE.read_text(encoding="utf-8"))
    feed_products = feed.get("products") or []
    home = HOME_FILE.read_text(encoding="utf-8")
    static_products = read_static_products(home)
    all_products = prepare_products(feed_products, static_products)

    global products_by_category
    products_by_category = defaultdict(list)
    for product in all_products:
        key = str(product.get("category") or "util")
        if key in CATEGORY_META:
            products_by_category[key].append(product)

    # Generate indexable category landing pages with real products in the initial HTML.
    update_candidates = [str(p.get("addedAt") or "") for p in feed_products if p.get("addedAt")]
    validated_date = str(feed.get("lastValidatedAt") or "")[:10]
    if re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", validated_date):
        update_candidates.append(validated_date)
    updated = max(update_candidates, default=str(date.today().isoformat()))
    generated_paths = []
    for key, products in products_by_category.items():
        if not products:
            continue
        meta = CATEGORY_META[key]
        page_dir = ROOT / "achados" / meta["slug"]
        page_dir.mkdir(parents=True, exist_ok=True)
        page_path = page_dir / "index.html"
        category_updated = max(
            [str(p.get("addedAt") or "") for p in products if p.get("addedAt")],
            default=updated,
        )
        content = category_page(key, meta, products, category_updated)
        page_path.write_text(content, encoding="utf-8")
        generated_paths.append((key, page_path, meta, products))

    # Server-render product cards in the homepage HTML, before any JavaScript runs.
    cards = "\n".join(card_html(p) for p in all_products)
    grid_open = re.search(r'<div\b[^>]*\bid="productGrid"[^>]*>', home)
    if not grid_open:
        raise RuntimeError("Não foi possível localizar o productGrid da página inicial.")
    div_tags = re.compile(r'</?div\b[^>]*>', re.I)
    depth = 1
    grid_close = None
    for tag in div_tags.finditer(home, grid_open.end()):
        if tag.group(0).lower().startswith("</div"):
            depth -= 1
        else:
            depth += 1
        if depth == 0:
            grid_close = tag.start()
            break
    if grid_close is None:
        raise RuntimeError("O bloco productGrid não possui fechamento HTML correspondente.")

    # Remove orphaned cards left behind by the earlier non-balanced HTML replacement.
    grid_close_end = grid_close + len("</div>")
    editorial_start = home.find('<section class="wrap editorial"', grid_close_end)
    if editorial_start >= 0:
        stale_tail = home[grid_close_end:editorial_start]
        if 'class="product-card"' in stale_tail or "VC:PRERENDERED_PRODUCTS_END" in stale_tail:
            home = home[:grid_close_end] + "\n</section>\n" + home[editorial_start:]

    grid_content = "\n<!-- VC:PRERENDERED_PRODUCTS_START -->\n" + cards + "\n<!-- VC:PRERENDERED_PRODUCTS_END -->\n"
    home = home[:grid_open.end()] + grid_content + home[grid_close:]

    # Embed the same feed in the initial document so the existing filters/search work immediately.
    safe_feed_json = json.dumps({"products": feed_products}, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    feed_script = '<script id="vc-prerendered-feed" type="application/json">' + safe_feed_json + "</script>\n"
    home = re.sub(r'<script id="vc-prerendered-feed" type="application/json">[\s\S]*?</script>\s*', "", home)
    if "</head>" not in home:
        raise RuntimeError("Não encontrei o fechamento do head em index.html.")
    home = home.replace("</head>", feed_script + "</head>", 1)

    bootstrap = r"""
// VC:PRELOADED_FEED_START
(function(){
  const node=document.getElementById('vc-prerendered-feed');
  if(!node)return;
  try{
    const feed=JSON.parse(node.textContent||'{}');
    const existing=new Set(products.map(p=>p.affiliateUrl).filter(Boolean));
    (Array.isArray(feed.products)?feed.products:[]).forEach(p=>{
      const affiliateUrl=String(p.affiliateUrl||'');
      const image=String(p.image||'');
      if(!affiliateUrl.startsWith('https://')||!image.startsWith('https://')||!p.name||existing.has(affiliateUrl))return;
      products.push({
        name:String(p.name),category:String(p.category||'util'),
        categoryName:String(p.categoryName||'Achados'),
        description:String(p.description||''),price:String(p.price||'Consulte na loja'),
        image,affiliateUrl,tag:String(p.tag||'SHOPEE • OFERTA AFILIADA'),
        icon:String(p.icon||'🛍️'),commissionRate:Number(p.commissionRate)||0,
        ratingStar:Number(p.ratingStar)||0,sales:Number(p.sales)||0,store:'Shopee'
      });
      existing.add(affiliateUrl);
    });
  }catch(error){console.warn('Feed pré-renderizado indisponível:',error);}
})();
// VC:PRELOADED_FEED_END
"""
    marker_start = "// VC:PRELOADED_FEED_START"
    marker_end = "// VC:PRELOADED_FEED_END"
    if marker_start in home and marker_end in home:
        start = home.index(marker_start)
        end = home.index(marker_end, start) + len(marker_end)
        home = home[:start] + bootstrap.strip() + home[end:]
    else:
        array_start = home.find("const products = [")
        array_end = home.find("\n];", array_start)
        if array_start < 0 or array_end < 0:
            raise RuntimeError("Não encontrei o fechamento do array products em index.html.")
        insert_at = array_end + len("\n];")
        home = home[:insert_at] + "\n" + bootstrap + home[insert_at:]

    # Turn the category tiles into ordinary crawlable HTML links.
    def link_category(match: re.Match) -> str:
        key = match.group(1)
        body = match.group(2)
        meta = CATEGORY_META.get(key)
        if not meta:
            return match.group(0)
        if key in products_by_category and products_by_category[key]:
            href = f"./achados/{meta['slug']}/"
        else:
            href = f"./{meta['guide']}"
        return f'<a class="catbox" data-target="{esc(key)}" href="{esc(href)}">{body}</a>'

    home, _ = re.subn(
        r'<div class="catbox" data-target="([a-z]+)">([\s\S]*?)</div>',
        link_category,
        home,
    )
    old_handler = """document.querySelectorAll('.catbox').forEach(box=>box.addEventListener('click',()=>{const cat=box.dataset.target;const filter=document.querySelector('.filter[data-cat="'+cat+'"]');if(filter){filter.click();document.getElementById('achados').scrollIntoView({behavior:'smooth'})}}));"""
    new_handler = """document.querySelectorAll('.catbox[data-target]').forEach(box=>box.addEventListener('click',()=>{if(box.tagName==='A')return;const cat=box.dataset.target;const filter=document.querySelector('.filter[data-cat="'+cat+'"]');if(filter){filter.click();document.getElementById('achados').scrollIntoView({behavior:'smooth'})}}));"""
    home = home.replace(old_handler, new_handler)

    # Measure affiliate clicks in GA4 from both server-rendered and hydrated product cards.
    tracking_start = "// VC:AFFILIATE_TRACKING_START"
    tracking_end = "// VC:AFFILIATE_TRACKING_END"
    if tracking_start in home and tracking_end in home:
        start = home.index(tracking_start)
        end = home.index(tracking_end, start) + len(tracking_end)
        home = home[:start] + home[end:]
    tracking = r"""// VC:AFFILIATE_TRACKING_START
if(!window.__vcAffiliateTrackingBound){
  window.__vcAffiliateTrackingBound=true;
  document.addEventListener('click',function(event){
    const link=event.target.closest('a[rel~="sponsored"]');
    if(!link || typeof gtag!=='function')return;
    const card=link.closest('.product-card,.card');
    const title=card?.querySelector('h2,h3')?.textContent?.trim() || link.getAttribute('aria-label') || '';
    const category=card?.querySelector('.product-category,.catlabel')?.textContent?.trim() || '';
    gtag('event','affiliate_click',{
      product_name:title,product_category:category,link_url:link.href,
      page_path:location.pathname,transport_type:'beacon'
    });
  });
}
// VC:AFFILIATE_TRACKING_END"""
    close_script = home.rfind("\n});\n</script>")
    if close_script < home.find("const products = ["):
        raise RuntimeError("Não encontrei o fechamento do script principal para instalar o rastreamento GA4.")
    home = home[:close_script] + "\n" + tracking + home[close_script:]

    HOME_FILE.write_text(home, encoding="utf-8")

    # Update an accurate sitemap: only generated category URLs are added; existing pages are preserved.
    tree = ET.parse(SITEMAP_FILE)
    root = tree.getroot()
    existing = {
        loc.text: url for url in root.findall("sm:url", NS)
        if (loc := url.find("sm:loc", NS)) is not None and loc.text
    }
    today = updated
    home_url = BASE_URL + "/"
    if home_url in existing:
        lastmod = existing[home_url].find("sm:lastmod", NS)
        if lastmod is None:
            lastmod = ET.SubElement(existing[home_url], f"{{{NS['sm']}}}lastmod")
        lastmod.text = today
    else:
        url = ET.SubElement(root, f"{{{NS['sm']}}}url")
        ET.SubElement(url, f"{{{NS['sm']}}}loc").text = home_url
        ET.SubElement(url, f"{{{NS['sm']}}}lastmod").text = today
        ET.SubElement(url, f"{{{NS['sm']}}}priority").text = "1.0"

    for key, page_path, meta, products in generated_paths:
        page_url = f"{BASE_URL}/achados/{meta['slug']}/"
        if page_url in existing:
            url = existing[page_url]
        else:
            url = ET.SubElement(root, f"{{{NS['sm']}}}url")
            ET.SubElement(url, f"{{{NS['sm']}}}loc").text = page_url
            ET.SubElement(url, f"{{{NS['sm']}}}priority").text = "0.8"
        lastmod = url.find("sm:lastmod", NS)
        if lastmod is None:
            lastmod = ET.SubElement(url, f"{{{NS['sm']}}}lastmod")
        lastmod.text = max((str(p.get("addedAt") or today) for p in products), default=today)

    ET.indent(tree, space="  ")
    ET.register_namespace("", NS["sm"])
    tree.write(SITEMAP_FILE, encoding="utf-8", xml_declaration=True)

    summary = {CATEGORY_META[key]["name"]: len(products) for key, products in products_by_category.items() if products}
    print(f"HTML inicial: {len(all_products)} produtos com imagem e link afiliado.")
    print(f"Páginas de categoria geradas: {len(generated_paths)}")
    print("Distribuição: " + ", ".join(f"{name}={count}" for name, count in summary.items()))
    print(f"Sitemap atualizado: {len(root.findall('sm:url', NS))} URLs.")


products_by_category: dict[str, list[dict]] = defaultdict(list)

if __name__ == "__main__":
    main()
