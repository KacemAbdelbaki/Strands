import logging
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger = logging.getLogger(__name__)


def _scrape_with_requests(url: str) -> str | None:
    """Fast, lightweight scrape using requests + BeautifulSoup.

    Returns clean Markdown text, or None if it fails / gets blocked.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("requests-based scrape failed for %s: %s", url, exc)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Detect login walls / empty content
    title_tag = soup.find("title")
    if title_tag and "login" in title_tag.get_text(strip=True).lower():
        logger.info("Login wall detected for %s — will try Playwright.", url)
        return None

    # Remove clutter
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "iframe"]):
        tag.extract()

    main = soup.find("main") or soup.find("article") or soup.find("body")
    if not main:
        return None

    markdown_text = md(str(main), heading_style="ATX")
    clean = "\n".join(line for line in markdown_text.splitlines() if line.strip())

    if len(clean) < 100:
        logger.info("Content too short (%d chars) for %s — will try Playwright.", len(clean), url)
        return None

    return clean


def _scrape_with_playwright(url: str) -> str | None:
    """Fallback scrape using headless Playwright + stealth.

    Handles JavaScript-rendered pages and login walls.
    Returns clean Markdown text, or None on failure.
    """
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import stealth_sync
    except ImportError:
        logger.warning(
            "Playwright not installed. Run: pip install playwright playwright-stealth && playwright install chromium"
        )
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            stealth_sync(page)

            logger.info("Playwright navigating to %s", url)
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # Give JS a moment to render
            page.wait_for_timeout(3000)

            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "iframe"]):
            tag.extract()

        main = soup.find("main") or soup.find("article") or soup.find("body")
        if not main:
            return None

        markdown_text = md(str(main), heading_style="ATX")
        clean = "\n".join(line for line in markdown_text.splitlines() if line.strip())
        return clean if len(clean) > 50 else None

    except Exception as exc:
        logger.error("Playwright scrape failed for %s: %s", url, exc, exc_info=True)
        return None


def scrape_webpage(url: str) -> str:
    """Scrapes a public web page and returns its text content in Markdown format.

    Uses a fast requests-based approach first; if that fails (JS-rendered page,
    login wall, empty content), falls back to a headless Playwright browser.

    Use this tool when you need to read the content of a specific URL provided
    by the user, or when you want to dive deeper into a link found via web search
    or job search results.

    Args:
        url: The full URL to scrape (e.g., 'https://example.com/job/12345')

    Returns:
        The content of the page in Markdown format, or an error message if it fails.
    """
    logger.info("Scraping URL: %s", url)

    # Attempt 1: fast requests-based scrape
    content = _scrape_with_requests(url)
    if content:
        if len(content) > 20000:
            logger.warning("Content from %s is very long (%d chars). Truncating.", url, len(content))
            content = content[:20000] + "\n\n...[Content truncated due to length]..."
        return content

    # Attempt 2: Playwright fallback for JS-rendered / blocked pages
    logger.info("Falling back to Playwright for %s", url)
    content = _scrape_with_playwright(url)
    if content:
        if len(content) > 20000:
            logger.warning("Content from %s is very long (%d chars). Truncating.", url, len(content))
            content = content[:20000] + "\n\n...[Content truncated due to length]..."
        return content

    return f"Error: Could not extract readable content from {url} using either method."
