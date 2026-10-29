import re
import urllib.parse
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from bs4 import BeautifulSoup

from app.core.exceptions import ParseError

RATING_MAP = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}


def parse_listing_page(html: str, base_url: str) -> tuple[list[str], Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    book_urls: list[str] = []

    for pod in soup.select("article.product_pod"):
        link = pod.select_one("h3 a")
        if link and link.get("href"):
            book_urls.append(urllib.parse.urljoin(base_url, link["href"]))

    next_link = soup.select_one("li.next a")
    next_url: Optional[str] = None
    if next_link and next_link.get("href"):
        next_url = urllib.parse.urljoin(base_url, next_link["href"])

    return book_urls, next_url


def extract_slug_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    segments = [s for s in parsed.path.strip("/").split("/") if s and s != "index.html"]
    # Look for segment ending in _<id>
    for segment in reversed(segments):
        if "_" in segment:
            return segment
    return segments[-1] if segments else "book"


def parse_detail_page(html: str, source_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    # Title: h1
    title_el = soup.find("h1")
    if not title_el:
        raise ParseError(f"Missing title element on page: {source_url}")
    title = title_el.get_text(strip=True)
    if not title:
        raise ParseError(f"Empty title on page: {source_url}")

    # Price: p.price_color
    price_el = soup.select_one("p.price_color")
    if not price_el:
        raise ParseError(f"Missing price element on page: {source_url}")
    price_text = price_el.get_text(strip=True)
    price_clean = re.sub(r"[^0-9.]", "", price_text)
    try:
        price = Decimal(price_clean).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ParseError(f"Invalid price '{price_text}' on page: {source_url}") from exc

    # Rating: p.star-rating
    star_el = soup.select_one("p.star-rating")
    if not star_el:
        raise ParseError(f"Missing star-rating element on page: {source_url}")
    classes = star_el.get("class", [])
    rating = next((RATING_MAP[c] for c in classes if c in RATING_MAP), None)
    if rating is None:
        raise ParseError(f"Unknown rating classes {classes} on page: {source_url}")

    # Category: ul.breadcrumb li:nth-child(3) a
    cat_el = soup.select_one("ul.breadcrumb li:nth-child(3) a")
    if not cat_el:
        raise ParseError(f"Missing category element on page: {source_url}")
    category = cat_el.get_text(strip=True)
    if not category:
        raise ParseError(f"Empty category on page: {source_url}")

    # Availability: p.instock.availability
    avail_el = soup.select_one("p.instock.availability")
    avail_raw = avail_el.get_text(strip=True) if avail_el else "Unknown"
    in_stock = "In stock" in avail_raw
    stock_match = re.search(r"\((\d+)\s+available\)", avail_raw)
    stock_count: Optional[int] = int(stock_match.group(1)) if stock_match else None

    # Description: #product_description ~ p
    desc_el = soup.select_one("#product_description ~ p")
    description: Optional[str] = desc_el.get_text(strip=True) if desc_el else None

    # UPC: table.table-striped tr:nth-child(1) td
    upc_el = soup.select_one("table.table-striped tr:nth-child(1) td")
    upc: Optional[str] = upc_el.get_text(strip=True) if upc_el else None

    # Image URL: #product_gallery img
    img_el = soup.select_one("#product_gallery img")
    image_url: Optional[str] = None
    if img_el and img_el.get("src"):
        image_url = urllib.parse.urljoin(source_url, img_el["src"])

    slug = extract_slug_from_url(source_url)

    return {
        "source_url": source_url,
        "slug": slug,
        "title": title,
        "price": price,
        "currency": "GBP",
        "rating": rating,
        "in_stock": in_stock,
        "stock_count": stock_count,
        "availability_raw": avail_raw,
        "category": category,
        "description": description,
        "upc": upc,
        "image_url": image_url,
    }
