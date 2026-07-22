"""Single entry point for the DuckDuckGo-first laptop price flow."""

import json
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import COUNTRY_CURRENCY
from config import LAPTOP_MODEL
from config import TARGET_COUNTRY
from exchange import convert_currency
from scraper import get_store_candidates, scrape_store, _score_title

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table


def build_report():
    """Build a structured report for the configured laptop model."""
    console = Console(stderr=True)
    target_currency = COUNTRY_CURRENCY[TARGET_COUNTRY]
    
    source_results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        
        search_task = progress.add_task(f"[cyan]Searching stores for '{LAPTOP_MODEL}'...", total=1)
        store_candidates = get_store_candidates(LAPTOP_MODEL, TARGET_COUNTRY)
        progress.update(search_task, completed=1, description=f"[green]Found {len(store_candidates)} store candidates")
        
        if store_candidates:
            scrape_task = progress.add_task("[cyan]Scraping stores in parallel...", total=len(store_candidates))
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_store = {
                    executor.submit(scrape_store, store, LAPTOP_MODEL): store 
                    for store in store_candidates
                }
                
                for future in as_completed(future_to_store):
                    store = future_to_store[future]
                    try:
                        results = future.result()
                        # results is now a list of products (or errors)
                        for result in results:
                            source_results.append(result)
                            if result.get("status") == "ok":
                                progress.console.print(f"[green]✔[/green] {store['source']}: Found [bold]{result.get('title')[:40]}...[/bold] at {result.get('price')} {result.get('currency')}")
                            else:
                                progress.console.print(f"[red]✖[/red] {store['source']}: Failed - {result.get('error', 'Unknown Error')}")
                    except Exception as exc:
                        source_results.append({
                            "source": store["source"],
                            "status": "error",
                            "error": str(exc),
                        })
                        progress.console.print(f"[red]✖[/red] {store['source']}: Error - {exc}")
                    finally:
                        progress.update(scrape_task, advance=1)
        else:
            source_results = [{
                "source": "DuckDuckGo",
                "status": "error",
                "error": "No supported store results were found in DuckDuckGo search",
            }]

    successful_results = []
    for result in source_results:
        if result.get("status") != "ok":
            continue

        result["converted_currency"] = target_currency
        result["converted_price"] = convert_currency(
            result["price"],
            result["currency"],
            target_currency,
        )
        if result["converted_price"] == 0.0:
            continue
            
        result["confidence_score"] = _score_title(result["title"], LAPTOP_MODEL)
        successful_results.append(result)
    import statistics
    if successful_results:
        max_score = max(r["confidence_score"] for r in successful_results)
        baseline_group = [r["converted_price"] for r in successful_results if r["confidence_score"] >= max_score - 5]
        
        if baseline_group:
            median_price = statistics.median(baseline_group)
            std_dev = statistics.pstdev(baseline_group) if len(baseline_group) > 1 else median_price * 0.2
            
            # Statistical bound allowance: median +/- 2 standard deviations
            lower_bound = max(median_price - (2 * std_dev), median_price * 0.4)
            upper_bound = median_price + (2 * std_dev)
            
            # Prevent incredibly tight bounds if all laptops happen to be exactly the same price
            if upper_bound - lower_bound < median_price * 0.2:
                lower_bound = median_price * 0.7
                upper_bound = median_price * 1.5
                
            filtered_results = []
            for r in successful_results:
                primary_price = r["converted_price"]
                
                # Safe Zone: If primary price is already within statistical bounds, do not snap it
                if lower_bound <= primary_price <= upper_bound:
                    filtered_results.append(r)
                else:
                    # Primary price is an anomaly. Scan all extracted prices for a valid one
                    best_price = None
                    if "all_prices" in r and r["all_prices"]:
                        for p_obj in r["all_prices"]:
                            conv_p = convert_currency(p_obj["price"], p_obj["currency"], target_currency)
                            if lower_bound <= conv_p <= upper_bound:
                                # Lock onto the valid price closest to the median
                                if best_price is None or abs(conv_p - median_price) < abs(best_price - median_price):
                                    best_price = conv_p
                                    
                    if best_price is not None:
                        r["converted_price"] = best_price
                        filtered_results.append(r)
                        
            successful_results = filtered_results
    # Map target country to its TLD
    country_tld_map = {
        "India": ".in",
        "United States": ".us",
        "USA": ".us",
        "United Kingdom": ".co.uk",
        "Germany": ".de",
        "France": ".fr",
        "Japan": ".jp",
        "Canada": ".ca",
        "Australia": ".com.au",
    }
    target_tld = country_tld_map.get(TARGET_COUNTRY, ".com")

    def get_domain_priority(url):
        domain = urlparse(url).netloc.lower()
        if domain.endswith(target_tld):
            return 0
        if domain.endswith(".com"):
            return 1
        return 2

    # Sort globally by:
    # 1. confidence_score (descending)
    # 2. domain_priority (ascending, so 0 is best)
    # 3. converted_price (ascending)
    successful_results.sort(key=lambda item: (
        -item["confidence_score"],
        get_domain_priority(item["url"]),
        item["converted_price"]
    ))
    
    # Enforce max 5 laptops per source (using the highest matching score)
    source_counts = {}
    all_results = []
    for result in successful_results:
        source = result["source"]
        if source_counts.get(source, 0) >= 5:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
        all_results.append(result)

    converted_prices = [result["converted_price"] for result in all_results]

    summary = {
        "target_country": TARGET_COUNTRY,
        "target_currency": target_currency,
        "total_laptops_found": len(all_results),
        "displayed_laptops": len(all_results),
    }

    if converted_prices:
        lowest = all_results[0]
        highest = all_results[-1]
        summary.update(
            {
                "lowest_price": lowest["converted_price"],
                "highest_price": highest["converted_price"],
                "average_price": round(sum(converted_prices) / len(converted_prices), 2),
            }
        )

    return {
        "config": {
            "target_country": TARGET_COUNTRY,
            "target_currency": target_currency,
            "laptop_model": LAPTOP_MODEL,
        },
        "sources": all_results,
        "summary": summary,
    }


def main():
    report = build_report()
    
    console = Console()
    
    # Generate beautiful table for output
    table = Table(title=f"Top Similar Laptops Found for '{LAPTOP_MODEL}'", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Store", style="cyan")
    table.add_column("Similar Laptop Found", style="white", overflow="fold")
    table.add_column("Match Score", justify="center", style="yellow")
    table.add_column(f"Price ({report['config']['target_currency']})", justify="right", style="green")
    table.add_column("Link", justify="center")

    for i, item in enumerate(report["sources"], start=1):
        price_str = f"{item['converted_price']:,.2f}"
        link_str = f"[link={item['product_url']}]Click Here[/link]"
        table.add_row(
            str(i),
            item['source'],
            item['title'],
            str(item.get('confidence_score', 0)),
            f"₹{price_str}" if report['config']['target_currency'] == 'INR' else f"${price_str}",
            link_str
        )

    console.print("\n")
    if not report["sources"]:
        console.print("[red]No laptops found matching your criteria.[/red]")
    else:
        console.print(table)
        
        currency_symbol = "₹" if report['config']['target_currency'] == 'INR' else "$"
        avg_price = report['summary'].get('average_price', 0)
        
        console.print(f"\n[bold]Summary:[/bold] Found [cyan]{report['summary']['total_laptops_found']}[/cyan] laptops in total. Displaying top [cyan]{report['summary']['displayed_laptops']}[/cyan]. Average Price: [green]{currency_symbol}{avg_price:,.2f}[/green]\n")


if __name__ == "__main__":
    main()