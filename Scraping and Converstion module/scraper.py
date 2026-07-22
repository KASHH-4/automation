"""DuckDuckGo-first laptop price scraping helpers with Universal Stores & Playwright Fallback."""

from __future__ import annotations

from html import unescape
import json
import re
from urllib.parse import parse_qs, quote_plus, unquote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from config import DDG_RESULTS_LIMIT, TARGET_COUNTRY, COUNTRY_CURRENCY

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
DDG_LITE_URL = "https://lite.duckduckgo.com/lite/"
IGNORED_TOKENS = {
    "gb", "ssd", "hdd", "ram", "with", "and", "the", "for", 
    "i3", "i5", "i7", "i9", "gen", "inch", "laptop", "notebook"
}


def _normalize_text(value) -> str:
    return re.sub(r"\s+", " ", unescape(str(value))).strip()


def _get_model_tokens(model):
    return [
        token for token in re.findall(r"[a-z0-9]+", model.lower())
        if token not in IGNORED_TOKENS and not token.isdigit()
    ]

def _score_title(title, model):
    title_lower = _normalize_text(title).lower()
    tokens = _get_model_tokens(model)
    if not tokens:
        return 0
    return sum(1 for token in tokens if token in title_lower)


def _fetch_html(url):
    response = requests.get(
        url,
        timeout=25,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    response.raise_for_status()
    return response.text


def _fetch_html_playwright(url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        page.goto(url, timeout=25000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)  # Wait for dynamic price rendering
        html = page.content()
        browser.close()
        return html


def _parse_price_number(raw_price):
    cleaned = re.sub(r"[^0-9.]", "", str(raw_price))
    if not cleaned:
        raise ValueError(f"Could not parse price from {raw_price!r}")
    return float(cleaned)


def _safe_json_loads(raw_json):
    cleaned = raw_json.strip()
    cleaned = cleaned.replace("\n", " ")
    cleaned = re.sub(r"^<!--", "", cleaned)
    cleaned = re.sub(r"-->$", "", cleaned)
    cleaned = re.sub(r"^<!\[CDATA\[", "", cleaned)
    cleaned = re.sub(r"\]\]>$", "", cleaned)
    return json.loads(cleaned)


def _json_ld_documents(html):
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(?P<json>.*?)</script>',
        html,
        re.S | re.I,
    ):
        raw_json = match.group("json").strip()
        if not raw_json:
            continue
        try:
            yield _safe_json_loads(raw_json)
        except Exception:
            continue


def _walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _extract_meta_value(html, names):
    for name in names:
        patterns = (
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\'](?P<content>[^"\']+)["\']',
            rf'<meta[^>]+content=["\'](?P<content>[^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']',
        )
        for pattern in patterns:
            match = re.search(pattern, html, re.I | re.S)
            if match:
                return _normalize_text(match.group("content"))
    return ""


def _extract_page_title(html):
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if not match:
        return ""
    return _normalize_text(match.group(1))


def _extract_offer_price(offers, default_currency):
    if isinstance(offers, list):
        for entry in offers:
            try:
                return _extract_offer_price(entry, default_currency)
            except ValueError:
                continue
        raise ValueError("No usable offer price found")

    if not isinstance(offers, dict):
        raise ValueError("Offer payload is not a dictionary")

    for key in ("price", "lowPrice", "highPrice"):
        value = offers.get(key)
        if value is None:
            continue
        currency = offers.get("priceCurrency") or offers.get("currency") or default_currency
        return _parse_price_number(value), currency

    price_specification = offers.get("priceSpecification")
    if isinstance(price_specification, dict):
        for key in ("price", "priceValue"):
            value = price_specification.get(key)
            if value is not None:
                currency = (
                    price_specification.get("priceCurrency")
                    or offers.get("priceCurrency")
                    or default_currency
                )
                return _parse_price_number(value), currency

    raise ValueError("No usable offer price found")


def _collect_product_candidates(html, page_url, default_currency, model=""):
    candidates = []

    # STRATEGY 1: JSON-LD (Highest accuracy)
    for document in _json_ld_documents(html):
        for node in _walk_json(document):
            if not isinstance(node, dict):
                continue
                
            node_type = node.get("@type")
            node_types = {node_type} if isinstance(node_type, str) else set(node_type or [])
            
            if "ItemList" in node_types:
                elements = node.get("itemListElement", [])
                if isinstance(elements, list):
                    for el in elements:
                        if isinstance(el, dict):
                            item = el.get("item")
                            if isinstance(item, dict) and item.get("@type") == "Product":
                                _extract_product_from_node(item, page_url, default_currency, candidates)
            
            if "Product" in node_types:
                _extract_product_from_node(node, page_url, default_currency, candidates)

    # STRATEGY 2: Fallback Meta Tags (For single product pages without JSON-LD)
    fallback_title = _extract_meta_value(html, ["og:title", "twitter:title", "name"])
    fallback_price = _extract_meta_value(html, ["product:price:amount", "og:price:amount"])
    fallback_currency = _extract_meta_value(html, ["product:price:currency", "og:price:currency"])

    if fallback_title and fallback_price:
        try:
            candidates.append({
                "title": fallback_title,
                "url": page_url,
                "price": round(_parse_price_number(fallback_price), 2),
                "currency": fallback_currency or default_currency,
            })
        except ValueError:
            pass

    # STRATEGY 3: Heuristic Product Container Extraction (For search pages without JSON-LD)
    soup = BeautifulSoup(html, "html.parser")
    # Identify container candidates (typically blocks that contain links, images, and prices)
    for container in soup.find_all(['div', 'li', 'article']):
        # Ignore huge layout containers by limiting text length
        text = container.get_text(separator=' ', strip=True)
        if not text or len(text) > 5000 or len(text) < 15:
            continue
            
        # Extract URL and Title
        a_tag = container.find('a', href=True)
        if a_tag:
            url = a_tag['href']
            if url.startswith('/'):
                parsed_page = urlparse(page_url)
                url = f"{parsed_page.scheme}://{parsed_page.netloc}{url}"
            title = _normalize_text(a_tag.get_text(strip=True) or container.get_text(separator=' ', strip=True)[:100])
        else:
            url = page_url
            title = fallback_title or _normalize_text(container.get_text(separator=' ', strip=True)[:100])
        
        # 1. Title validation (Ensure title has brand/model keywords if model is provided)
        if model:
            tokens_in_model = _get_model_tokens(model)
            matched_tokens = sum(1 for t in tokens_in_model if t in title.lower())
            if tokens_in_model and matched_tokens == 0:
                continue
                
        # 2. Score container features
        score = 0
        if container.find('img'):
            score += 1
        score += 2 # Has URL
        
        # Negative keywords to drop advertisements or fake prices
        text_lower = text.lower()
        if any(word in text_lower for word in ["sponsored", "advertisement", "deal ends", "cashback", "exchange", "emi"]):
            score -= 5
            
        if score < 1:
            continue
            
        # 3. Extract Price
        # Look for typical price patterns like ₹54,990 or Rs. 54,990 or 54,990 INR
        price_match = re.search(r'(₹|rs\.?|inr|usd|\$|eur|€|£)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)', text, re.I)
        extracted_currency = default_currency
        
        if price_match:
            sym = price_match.group(1).lower()
            if sym in ["₹", "rs", "rs.", "inr"]:
                extracted_currency = "INR"
            elif sym in ["$", "usd"]:
                extracted_currency = "USD"
            elif sym in ["€", "eur"]:
                extracted_currency = "EUR"
            elif sym in ["£", "gbp"]:
                extracted_currency = "GBP"
            
            raw_number = price_match.group(2)
        else:
            raw_number = None
            
        if raw_number:
            try:
                price = _parse_price_number(raw_number)
                # Validate realistic price bounds based on extracted currency
                min_price = 10000 if extracted_currency == "INR" else 100
                max_price = 2500000 if extracted_currency == "INR" else 10000
                
                if price >= min_price and price <= max_price:
                    candidates.append({
                        "title": title,
                        "url": url,
                        "price": round(price, 2),
                        "currency": extracted_currency,
                    })
            except ValueError:
                pass

    # Deduplicate results using normalized title and price to merge strategies
    unique_candidates = []
    seen = set()
    for c in candidates:
        key = f"{c['title'].lower()}_{c['price']}"
        if key not in seen:
            seen.add(key)
            unique_candidates.append(c)

    return unique_candidates


def _extract_product_from_node(node, page_url, default_currency, candidates):
    title = _normalize_text(node.get("name") or node.get("title") or "")
    if not title:
        return

    offers = node.get("offers")
    if offers is None:
        return
    try:
        price, currency = _extract_offer_price(offers, default_currency)
    except ValueError:
        return

    product_url = _normalize_text(node.get("url") or page_url)
    candidates.append({
        "title": title,
        "url": product_url,
        "price": round(price, 2),
        "currency": currency,
    })


def _get_top_candidates(candidates, model, fallback_title="", max_results=5):
    if not candidates:
        return []

    valid_candidates = []
    # Penalize accessories and low prices
    negative_words = {"case", "cover", "sleeve", "charger", "adapter", "skin", "protector", "refurbished", "keyboard", "bag", "mouse"}
    
    # Calculate total expected tokens in model
    tokens_in_model = len(_get_model_tokens(model))
    
    for c in candidates:
        # Minimum sensible price for a laptop to filter out EMI and accessories
        if c["price"] < 10000 and c["currency"] == "INR":
            continue
        if c["price"] < 100 and c["currency"] != "INR":
            continue
            
        penalty = 0
        title_lower = c["title"].lower()
        for word in negative_words:
            if word in title_lower:
                penalty += 10
        
        # Penalize questions/articles
        if "?" in c["title"]:
            penalty += 10
                
        title_score = _score_title(c["title"], model)
        fallback_score = _score_title(fallback_title, model) if fallback_title else 0
        
        # VERY STRICT FILTER:
        # If the item's title score is completely 0, AND the fallback (page title) score is 0,
        if title_score == 0 and fallback_score == 0:
            continue
            
        # Relaxed match: allow partial matches for discovery
        if tokens_in_model > 1 and max(title_score, fallback_score) < (tokens_in_model * 0.2):
            continue
            
        valid_candidates.append((c, penalty, title_score, fallback_score))

    if not valid_candidates:
        return []

    def sort_key(item_tuple):
        item, penalty, title_score, fallback_score = item_tuple
        return (-penalty, title_score, fallback_score, -item["price"])

    valid_candidates.sort(key=sort_key, reverse=True)
    
    # Return top N candidates, preserving uniqueness of title
    unique_titles = set()
    top_candidates = []
    for item_tuple in valid_candidates:
        item = item_tuple[0]
        if item["title"] not in unique_titles:
            unique_titles.add(item["title"])
            top_candidates.append(item)
            if max_results and len(top_candidates) >= max_results:
                break
                
    return top_candidates


def _search_duckduckgo_html(query, max_results):
    from ddgs import DDGS
    results = []
    blocked_domains = {"youtube.com", "tiktok.com", "instagram.com", "facebook.com", "reddit.com", "twitter.com", "carousell.ph"}
    
    try:
        with DDGS() as ddgs:
            for rank, r in enumerate(ddgs.text(query, max_results=max_results), start=1):
                url = r.get("href", "")
                domain = urlparse(url).netloc.lower()
                
                # Check if it's a blocked domain
                if any(blocked in domain for blocked in blocked_domains):
                    continue
                    
                results.append({
                    "title": _normalize_text(r.get("title", "")),
                    "url": url,
                    "rank": rank,
                })
    except Exception as e:
        pass # Ignore rate limits quietly
    return results


def _store_from_url(url):
    host = urlparse(url).netloc.lower()
    host = host.replace("www.", "")
    name = host.split(".")[0]
    return {
        "name": name,
        "display_name": host,
        "currency": COUNTRY_CURRENCY.get(TARGET_COUNTRY, "USD"), # Default to target country currency
    }


def _filter_unique_stores(search_results):
    filtered = []
    seen_counts = {}
    
    for item in search_results:
        store_config = _store_from_url(item["url"])
        store_name = store_config["name"]
        
        count = seen_counts.get(store_name, 0)
        if count >= 3:
            continue
            
        seen_counts[store_name] = count + 1
        filtered.append({
            **item,
            "source": store_config["display_name"],
            "store_name": store_name,
            "store_config": store_config,
        })
    return filtered


def scrape_store(store_hit, model):
    store_config = store_hit["store_config"]
    source_name = store_config["display_name"]
    default_currency = store_config["currency"]
    candidate_url = store_hit["url"]

    html = None
    top_candidates = []
    last_error = None
    
    # Attempt 1: Standard Requests
    try:
        html = _fetch_html(candidate_url)
        candidates = _collect_product_candidates(html, candidate_url, default_currency, model=model)
        top_candidates = _get_top_candidates(candidates, model, fallback_title=store_hit.get("title", ""), max_results=None)
    except Exception as exc:
        last_error = exc

    # Attempt 2: Playwright Fallback (If requests failed or no valid product found)
    if not top_candidates:
        try:
            html = _fetch_html_playwright(candidate_url)
            candidates = _collect_product_candidates(html, candidate_url, default_currency, model=model)
            top_candidates = _get_top_candidates(candidates, model, fallback_title=store_hit.get("title", ""), max_results=None)
        except Exception as exc:
            last_error = exc

    results = []
    for item in top_candidates:
        results.append({
            "source": source_name,
            "store_name": store_config["name"],
            "search_result_url": store_hit["url"],
            "search_result_title": store_hit.get("title", ""),
            "url": candidate_url,
            "product_url": item["url"],
            "title": item["title"],
            "price": round(item["price"], 2),
            "currency": item["currency"],
            "status": "ok",
        })

    if not results:
        results.append({
            "source": source_name,
            "store_name": store_config["name"],
            "search_result_url": store_hit["url"],
            "search_result_title": store_hit.get("title", ""),
            "url": candidate_url,
            "status": "error",
            "error": str(last_error) if last_error else "No valid product candidate found after fallback",
        })
        
    return results


def get_store_candidates(model, target_country):
    from config import SUPPORTED_STORES
    search_queries = [
        f"{model} {target_country}".strip(),
        model.strip(),
        f"{model} buy online".strip(),
    ]

    search_results = []
    # 1. Broad discovery
    for query in search_queries:
        res = _search_duckduckgo_html(query, DDG_RESULTS_LIMIT)
        if res:
            search_results.extend(res)
            break

    # 2. Targeted store discovery (to guarantee we check major retailers and get PRODUCT pages)
    for store_config in SUPPORTED_STORES:
        domain = store_config["domains"][0]
        site_query = f"site:{domain} {model} laptop"
        res = _search_duckduckgo_html(site_query, 3) # Top 3 product pages from this store
        if res:
            search_results.extend(res)

    unique_results = _filter_unique_stores(search_results)
    return unique_results