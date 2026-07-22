# Context

This project runs a resilient, DuckDuckGo-first laptop price pipeline that discovers e-commerce websites and scrapes them, falling back to headless browsers if necessary, before returning an organized table of products.

## System Architecture & Workflow

The architecture is built for **resilience and massive scale discovery**. Here is the exact Multi-Strategy workflow implemented in the system:

1. **Initialization (`config.py`)**
   - The user defines the `TARGET_COUNTRY` (e.g. India) and the `LAPTOP_MODEL` (e.g. HP Victus).
   - The `COUNTRY_CURRENCY` mapping is used to determine what currency the prices should be converted to at the end.
   - It stores a backup list of `SUPPORTED_STORES` to fall back on.

2. **Targeted Organic Store Discovery (`scraper.py`)**
   - The script uses the `ddgs` API to organically search the web for the laptop model, specifically targeting site operators (e.g., `site:amazon.in HP Victus`). This guarantees the scraper visits product pages on major retailers while also freely discovering new unique domains.

3. **Parallel Scraping Execution (`main.py` -> `scraper.py`)**
   - The `main.py` script utilizes `ThreadPoolExecutor` to dispatch the store URLs across concurrent worker threads (max 4).
   - The `rich.progress` library is used to present a live CLI dashboard.

4. **Multi-Strategy Container Extraction Pipeline (`scraper.py`)**
   Instead of a single point of failure, the script executes multiple overlapping extraction strategies and merges the results:
   
   - **Strategy 1: JSON-LD Extraction**
     It looks for `ItemList` and `Product` schemas hidden in the background code by website developers.
   
   - **Strategy 2: Meta Tags Fallback**
     It looks for `OpenGraph` tags (`product:price:amount`).
   
   - **Strategy 3: Heuristic Product Container Extraction**
     If the page is a search grid that lacks structured data (like Amazon/Flipkart), the scraper visually parses the HTML using `BeautifulSoup`. It identifies localized product blocks (e.g. `<div>` or `<li>` cards), scores them based on the presence of images, product links, pricing patterns (e.g. `₹55,000`), and laptop keywords. It rejects false positives (e.g. "EMI", "Cashback", "Sponsored").
   
   - **Attempt 1 vs Attempt 2**
     If standard `requests` fetching fails due to 403 Forbidden or missing DOM elements, `playwright.sync_api` is triggered to fully render the page and JavaScript before parsing.

5. **Heuristic Cross-Referencing & Deduplication**
   - **Price Bounds**: Ignores any item under 10,000 INR or over 2,500,000 INR (or $100 and $10,000 for USD) to filter out fake accessories and spam.
   - **Title Validation & Match Score**: Evaluates the extracted title based on exact model token matches. Titles containing `?` or negative keywords (e.g., "cover", "refurbished") are heavily penalized.
   - **Maximum Discovery**: It allows up to 3 links per store to be tested, scaling the amount of discovered products significantly.
   - **Relaxed Structure**: The scraper dynamically extracts prices even from massive product cards (up to 5000 characters) and single-product pages without strict link (`<a>`) anchors.

6. **Beautiful Table Output (`main.py`)**
   - All prices are aggressively converted using the primary `frankfurter.dev` API (`exchange.py`). If a specific regional currency (e.g. EGP, ZAR) is unsupported, it automatically falls back to the `open.er-api.com` API to prevent crashes.
   - The results are displayed cleanly using `rich.table`, creating a responsive dashboard sorted dynamically by **Match Score** (highest relevancy first), with clickable hyperlinked URLs.

## Libraries Breakdown

The dependencies in `requirements.txt` power the following capabilities:

- **`requests`**: Used as the primary, high-speed HTTP client to fetch website HTML.
- **`beautifulsoup4`**: The core parsing engine used for the Heuristic Product Container Extraction strategy. It allows us to safely navigate the DOM tree and isolate individual laptop cards.
- **`playwright`**: Used as a heavy-duty fallback scraper. If a site relies heavily on React/JavaScript or blocks basic requests, Playwright launches a real headless Chromium browser to render the DOM fully.
- **`ddgs`**: The DuckDuckGo search wrapper used to organically discover laptop listings and stores without needing API keys.
- **`rich`**: Powers the stunning terminal UI. It is responsible for the live progress bars (`rich.progress`) during concurrent scraping and the finalized `rich.table` output.
- **`greenlet` & `idna` & `lxml` & `colorama` & `click`**: Secondary dependencies implicitly required by `playwright`, `requests`, `duckduckgo-search`, and `rich` for networking, XML parsing, and terminal coloring.

## Run Steps

From the workspace root, use your personal conda environment:

1. Run `setup-conda` in PowerShell.
2. Run `conda create --prefix ./env python -y` if the local environment does not already exist.
3. Run `conda activate ./env`.
4. Run `python -m pip install -r requirements.txt`.
5. Run `playwright install chromium` inside the active environment.
6. Run `python main.py` or `conda run --prefix ./env python main.py`.