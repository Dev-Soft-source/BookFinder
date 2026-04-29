from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import BackgroundTasks
from typing import Dict, Optional, Union
from urllib.parse import urlencode
import math
import asyncio
import os
import logging
import time
import sys
from pathlib import Path
import random
import re

from playwright.async_api import (
    Browser,
    BrowserContext,
    Playwright,
    TimeoutError as AsyncPlaywrightTimeoutError,
    async_playwright,
)
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from backend.openai_image_numbers import (
#from openai_image_numbers import (
    DEFAULT_URL,
    _human_delay,
    click_amzn_captcha_verify_button,
    run_post_load_captcha_and_screenshot,
)

# Windows + Playwright: subprocess-capable loop when this module loads before main (e.g. tests).
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


def _windows_async_playwright_unsupported() -> bool:
    """True when the running loop cannot spawn Playwright's driver (e.g. uvicorn --reload)."""
    if sys.platform != "win32":
        return False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False
    return not isinstance(loop, asyncio.ProactorEventLoop)


_sync_playwright_fallback_logged = False

logger = logging.getLogger(__name__)

SEARCH_URL = "https://bookfinder.com/isbn/"  # or the exact endpoint you discover


class BookFinderRateLimited(Exception):
    """HTTP 429 from BookFinder — caller should wait before retrying."""

    def __init__(self, message: str, *, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


def _retry_after_seconds_from_response(response) -> Optional[float]:
    """Parse ``Retry-After`` as delay in seconds (Playwright sync/async response)."""
    if response is None:
        return None
    try:
        headers = response.headers
    except Exception:
        return None
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(str(raw).strip()))
    except ValueError:
        return None


def _bookfinder_storage_state_path() -> Path:
    """Session JSON from sync CAPTCHA; async fetch loads it for the same cookies."""
    custom = os.environ.get("BOOKFINDER_STORAGE_STATE_PATH")
    if custom:
        return Path(custom)
    return Path(__file__).resolve().parent / ".bookfinder_playwright_storage.json"


# Sync CAPTCHA warmup runs in a worker thread (see asyncio.to_thread); guard "once" per process.
_captcha_warmup_once_done = False
_captcha_warmup_lock = asyncio.Lock()

# --- Playwright (shared browser for all scrapes) ---
_pw: Optional[Playwright] = None
_browser: Optional[Browser] = None
_browser_lock = asyncio.Lock()

# One async BrowserContext for all ISBN fetches — created from the reCAPTCHA ``storage_state``
# (first sync session). Closed after a new ``pass_captcha`` so cookies reload from disk.
_bf_fetch_context: Optional[BrowserContext] = None
_bf_fetch_context_lock = asyncio.Lock()


async def _close_bookfinder_fetch_context() -> None:
    """Drop cached async context (e.g. after a new CAPTCHA session is saved)."""
    global _bf_fetch_context
    async with _bf_fetch_context_lock:
        if _bf_fetch_context is not None:
            try:
                await _bf_fetch_context.close()
            except Exception:
                logger.exception("Error closing BookFinder fetch context")
            _bf_fetch_context = None


async def _ensure_browser() -> Browser:
    global _pw, _browser
    async with _browser_lock:
        if _browser is None:
            _pw = await async_playwright().start()
            _browser = await _pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
        return _browser


async def shutdown_playwright() -> None:
    """Close the shared Playwright browser; safe to call multiple times."""
    global _pw, _browser
    await _close_bookfinder_fetch_context()
    async with _browser_lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _pw is not None:
            await _pw.stop()
            _pw = None

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

countries = {
    'AD': 'Andorra',
    'AE': 'United Arab Emirates',
    'AF': 'Afghanistan',
    'AG': 'Antigua and Barbuda',
    'AI': 'Anguilla',
    'AL': 'Albania',
    'AM': 'Armenia',
    'AO': 'Angola',
    'AQ': 'Antarctica',
    'AR': 'Argentina',
    'AS': 'American Samoa',
    'AT': 'Austria',
    'AU': 'Australia',
    'AW': 'Aruba',
    'AX': 'Åland Islands',
    'AZ': 'Azerbaijan',
    'BA': 'Bosnia and Herzegovina',
    'BB': 'Barbados',
    'BD': 'Bangladesh',
    'BE': 'Belgium',
    'BF': 'Burkina Faso',
    'BG': 'Bulgaria',
    'BH': 'Bahrain',
    'BI': 'Burundi',
    'BJ': 'Benin',
    'BL': 'Saint Barthelemy',
    'BM': 'Bermuda',
    'BN': 'Brunei Darussalam',
    'BO': 'Bolivia',
    'BQ': 'Bonaire',
    'BR': 'Brazil',
    'BS': 'Bahamas',
    'BT': 'Bhutan',
    'BV': 'Bouvet Island',
    'BW': 'Botswana',
    'BY': 'Belarus',
    'BZ': 'Belize',
    'CA': 'Canada',
    'CC': 'Cocos Islands',
    'CD': 'Democratic Republic of the Congo',
    'CF': 'Central African Republic',
    'CG': 'Republic of the Congo',
    'CH': 'Switzerland',
    'CI': "Cote d'Ivoire",
    'CK': 'Cook Islands',
    'CL': 'Chile',
    'CM': 'Cameroon',
    'CN': 'China',
    'CO': 'Colombia',
    'CR': 'Costa Rica',
    'CU': 'Cuba',
    'CV': 'Cape Verde',
    'CW': 'Curacao',
    'CX': 'Christmas Island',
    'CY': 'Cyprus',
    'CZ': 'Czech Republic',
    'DE': 'Germany',
    'DJ': 'Djibouti',
    'DK': 'Denmark',
    'DM': 'Dominica',
    'DO': 'Dominican Republic',
    'DZ': 'Algeria',
    'EC': 'Ecuador',
    'EE': 'Estonia',
    'EG': 'Egypt',
    'EH': 'Western Sahara',
    'ER': 'Eritrea',
    'ES': 'Spain',
    'ET': 'Ethiopia',
    'FI': 'Finland',
    'FJ': 'Fiji',
    'FK': 'Falkland Islands',
    'FM': 'Micronesia',
    'FO': 'Faroe Islands',
    'FR': 'France',
    'GA': 'Gabon',
    'GB': 'United Kingdom',
    'GD': 'Grenada',
    'GE': 'Georgia',
    'GF': 'French Guiana',
    'GG': 'Guernsey',
    'GH': 'Ghana',
    'GI': 'Gibraltar',
    'GL': 'Greenland',
    'GM': 'Gambia',
    'GN': 'Guinea',
    'GP': 'Guadeloupe',
    'GQ': 'Equatorial Guinea',
    'GR': 'Greece',
    'GS': 'South Georgia and South Sandwich',
    'GT': 'Guatemala',
    'GU': 'Guam',
    'GW': 'Guinea-Bissau',
    'GY': 'Guyana',
    'HK': 'Hong Kong',
    'HM': 'Heard and McDonald Islands',
    'HN': 'Honduras',
    'HR': 'Croatia',
    'HT': 'Haiti',
    'HU': 'Hungary',
    'ID': 'Indonesia',
    'IE': 'Ireland',
    'IL': 'Israel',
    'IM': 'Isle of Man',
    'IN': 'India',
    'IO': 'British Indian Ocean Territory',
    'IQ': 'Iraq',
    'IR': 'Iran',
    'IS': 'Iceland',
    'IT': 'Italy',
    'JE': 'Jersey',
    'JM': 'Jamaica',
    'JO': 'Jordan',
    'JP': 'Japan',
    'KE': 'Kenya',
    'KG': 'Kyrgyzstan',
    'KH': 'Cambodia',
    'KI': 'Kiribati',
    'KM': 'Comoros',
    'KN': 'Saint Kitts and Nevis',
    'KP': 'North Korea',
    'KR': 'South Korea',
    'KW': 'Kuwait',
    'KY': 'Cayman Islands',
    'KZ': 'Kazakhstan',
    'LA': 'Laos',
    'LB': 'Lebanon',
    'LC': 'Saint Lucia',
    'LI': 'Liechtenstein',
    'LK': 'Sri Lanka',
    'LR': 'Liberia',
    'LS': 'Lesotho',
    'LT': 'Lithuania',
    'LU': 'Luxembourg',
    'LV': 'Latvia',
    'LY': 'Libya',
    'MA': 'Morocco',
    'MC': 'Monaco',
    'MD': 'Moldova',
    'ME': 'Montenegro',
    'MF': 'Saint Martin',
    'MG': 'Madagascar',
    'MH': 'Marshall Islands',
    'MK': 'Macedonia',
    'ML': 'Mali',
    'MM': 'Myanmar',
    'MN': 'Mongolia',
    'MO': 'Macao',
    'MP': 'Northern Mariana Islands',
    'MQ': 'Martinique',
    'MR': 'Mauritania',
    'MS': 'Montserrat',
    'MT': 'Malta',
    'MU': 'Mauritius',
    'MV': 'Maldives',
    'MW': 'Malawi',
    'MX': 'Mexico',
    'MY': 'Malaysia',
    'MZ': 'Mozambique',
    'NA': 'Namibia',
    'NC': 'New Caledonia',
    'NE': 'Niger',
    'NF': 'Norfolk Island',
    'NG': 'Nigeria',
    'NI': 'Nicaragua',
    'NL': 'Netherlands',
    'NO': 'Norway',
    'NP': 'Nepal',
    'NR': 'Nauru',
    'NU': 'Niue',
    'NZ': 'New Zealand',
    'OM': 'Oman',
    'PA': 'Panama',
    'PE': 'Peru',
    'PF': 'French Polynesia',
    'PG': 'Papua New Guinea',
    'PH': 'Philippines',
    'PK': 'Pakistan',
    'PL': 'Poland',
    'PM': 'St. Pierre and Miquelon',
    'PN': 'Pitcairn',
    'PR': 'Puerto Rico',
    'PS': 'Palestine',
    'PT': 'Portugal',
    'PW': 'Palau',
    'PY': 'Paraguay',
    'QA': 'Qatar',
    'RE': 'Réunion',
    'RO': 'Romania',
    'RS': 'Serbia',
    'RU': 'Russia',
    'RW': 'Rwanda',
    'SA': 'Saudi Arabia',
    'SB': 'Solomon Islands',
    'SC': 'Seychelles',
    'SD': 'Sudan',
    'SE': 'Sweden',
    'SG': 'Singapore',
    'SH': 'St. Helena',
    'SI': 'Slovenia',
    'SJ': 'Svalbard and Jan Mayen Islands',
    'SK': 'Slovakia',
    'SL': 'Sierra Leone',
    'SM': 'San Marino',
    'SN': 'Senegal',
    'SO': 'Somalia',
    'SR': 'Suriname',
    'SS': 'South Sudan',
    'ST': 'Sao Tome and Principe',
    'SV': 'El Salvador',
    'SX': 'Sint Maarten',
    'SY': 'Syria',
    'SZ': 'Swaziland',
    'TC': 'Turks and Caicos Islands',
    'TD': 'Chad',
    'TF': 'French Southern Territories',
    'TG': 'Togo',
    'TH': 'Thailand',
    'TJ': 'Tajikistan',
    'TK': 'Tokelau',
    'TL': 'Timor-Leste',
    'TM': 'Turkmenistan',
    'TN': 'Tunisia',
    'TO': 'Tonga',
    'TR': 'Turkey',
    'TT': 'Trinidad and Tobago',
    'TV': 'Tuvalu',
    'TW': 'Taiwan',
    'TZ': 'Tanzania',
    'UA': 'Ukraine',
    'UG': 'Uganda',
    'UM': 'US Minor Outlying Islands',
    'US': 'United States',
    'UY': 'Uruguay',
    'UZ': 'Uzbekistan',
    'VA': 'Vatican City',
    'VC': 'Saint Vincent and the Grenadines',
    'VE': 'Venezuela',
    'VG': 'British Virgin Islands',
    'VI': 'Virgin Islands (US)',
    'VN': 'Vietnam',
    'VU': 'Vanuatu',
    'WF': 'Wallis and Futuna Islands',
    'WS': 'Samoa',
    'YE': 'Yemen',
    'YT': 'Mayotte',
    'ZA': 'South Africa',
    'ZM': 'Zambia',
    'ZW': 'Zimbabwe'
}

def best_buyback_price_from_Html(soup: BeautifulSoup) -> Optional[Dict[str, str]]:
    """Extracts the best buyback price ($) and book title from the HTML soup."""
    # Extract title
    title = None
    h1_tag = soup.select_one("h1")
    if h1_tag:
        a_tag = h1_tag.find("a")
        if a_tag:
            title = a_tag.get_text(strip=True)
        else:
            title = h1_tag.get_text(strip=True)

    # Extract buyback info
    a_tag = soup.find("a", attrs={"data-csa-c-clickouttype": "buyback"})
    if a_tag:
        buyback_link = a_tag.get("href")
        span_tag = a_tag.find("span")
        if span_tag:
            value_text = span_tag.get_text(strip=True).replace("$", "")
            try:
                return {
                    "title": title,
                    "buyback_price": float(value_text),
                    "buyback_link": buyback_link,
                } # type: ignore
            except ValueError:
                pass  # Invalid price text
    return {
        "title": title,
        "buyback_price": 0.0,
        "buyback_link": "",
    } # type: ignore

def get_scraping_data_from_Html(soup: BeautifulSoup, condition: str, isbn: str, filters: dict) -> Dict[str, Union[str, float, None]]:
    """Extracts the lowest price ($) for a given condition ('new' or 'used') from the HTML soup."""
    
    banned_sellers = filters.get("sellers", [])
    banned_countries = filters.get("countries", [])
    banned_websites = filters.get("websites", [])   

    #print(f"Evaluating seller: {banned_sellers}, location: {banned_countries}, link: {banned_websites}")
    max_retries = 3
    backoff_base = 1.5
    attempt = 0
    while attempt <= max_retries:
        tags = soup.find_all("div", attrs={"data-csa-c-offerstype": condition})
        buy_price = 0.0
        seller_name = ""
        seller_country = ""
        buy_link = ""
        if tags:
            div_tags = tags[0].find_all("div", attrs={"data-csa-c-condition": condition})
            
            # pageSizeHtml = tags[0].select_one("span")
            # if pageSizeHtml:
            #     match = re.search(r'of (\d+)', pageSizeHtml.get_text())
            #     if match:
            #         total = int(match.group(1))
            #         if total > 50:
                        # total_pages = math.ceil(total / 50)
                        # for page in range(2, total_pages + 1):
                        #     url = "https://bookfinder.com/isbn/" + isbn +"/?searchOffersType=" + condition + "&page=" + str(page)
                        #     resp = requests.Session().get(url, headers=DEFAULT_HEADERS, timeout=50)
                        #     if resp.status_code == 200:
                        #         soup_page = BeautifulSoup(resp.text, "html.parser")
                        #         tags_page = soup_page.find_all("div", attrs={"data-csa-c-offerstype": condition})
                        #         if tags_page:
                        #             div_tags_page = tags_page[0].find_all("div", attrs={"data-csa-c-condition": condition})
                        #             div_tags.extend(div_tags_page)
                    
            # print(f"Found {len(div_tags)} div tags with condition '{condition}'")

            for div_tag in div_tags:
                a_tag = div_tag.select_one("a", attrs={"data-csa-c-condition": condition})
                description = div_tag.get_text(strip=True) if div_tag else ""  
                
                if "kindle" in description.lower():
                    continue
                
                if not a_tag:
                    continue

                seller_name = (a_tag.get("data-csa-c-seller") or div_tag.get("data-csa-c-seller") or "")
                seller_location = a_tag.get("data-csa-c-sellerlocation", "")
                buy_link = a_tag.get("href", "")

                # Ensure seller_name is always a string
                if isinstance(seller_name, list):
                    seller_name = seller_name[0] if seller_name else ""
                if seller_name is None:
                    seller_name = ""

                if isinstance(seller_location, str):
                    # ensure seller_country is always a string (default to empty string) so .lower() is safe
                    seller_country = countries.get(seller_location, "")

                # Case-insensitive, partial match filtering
                if any(b.lower() in str(seller_name).lower().strip() for b in banned_sellers):
                    continue
                if any(b.lower() in seller_country.lower() for b in banned_countries):
                    continue
                if any(banned_site in buy_link for banned_site in banned_websites):
                    continue

                price_span = div_tag.select_one("span")
                if price_span:
                    text = price_span.get_text(strip=True)
                    try:
                        usd_price = safe_float(text.replace("$", "").replace(",", ""))
                        buy_price = round(usd_price, 2)
                    except ValueError:
                        logger.warning(f"Invalid price text '{text}' for seller {seller_name}")
                        buy_price = 0.0
                else:
                    logger.warning(f"No price span found for seller {seller_name}")
                    buy_price = 0.0

                break
            # Normalize types to satisfy type checker (BeautifulSoup attribute values can be lists or other types)
            if isinstance(seller_name, list):
                seller_name_norm = seller_name[0] if seller_name else ""
            else:
                seller_name_norm = str(seller_name) if seller_name is not None else ""

            seller_country_norm = str(seller_country) if seller_country is not None else ""
            buy_link_norm = str(buy_link) if buy_link is not None else ""

            return { "seller_name": seller_name_norm, "buy_price": buy_price, "seller_country": seller_country_norm, "buy_link": buy_link_norm, }
        else:
            wait = backoff_base ** attempt + random.random()
            time.sleep(wait)
            attempt += 1
    return { "seller_name": "", "buy_price": 0.0, "seller_country": "", "buy_link": "" }

def safe_float(value) -> float:
    """Convert a BeautifulSoup attribute value to float safely."""
    if value is None:
        return 0.0
    if isinstance(value, list):  # AttributeValueList case
        value = value[0] if value else "0"
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# Parse search HTML and extract data
def parse_search_html(html: str, isbn: str, filters: dict) -> Dict[str, Union[float, list, None]]:
    """Parse the BookFinder search results HTML and extract desired fields."""
    soup = BeautifulSoup(html, "html.parser")

    lowest_new = get_scraping_data_from_Html(soup, "NEW", isbn, filters)
    lowest_used = get_scraping_data_from_Html(soup, "USED", isbn, filters)

    lowest_new_price = safe_float(lowest_new.get("buy_price")) if isinstance(lowest_new, dict) else None
    lowest_used_price = safe_float(lowest_used.get("buy_price")) if isinstance(lowest_used, dict) else None

    #print(f"lowest_new: {lowest_new}, lowest_used: {lowest_used}")
    
    if lowest_new_price == 0 and lowest_used_price != 0:
        seller_name = lowest_used.get("seller_name")
        seller_country = lowest_used.get("seller_country")
        buy_link = lowest_used.get("buy_link")
        buy_price = lowest_used.get("buy_price")    
        condition = "USED"
    elif lowest_used_price == 0 and lowest_new_price != 0:
        seller_name = lowest_new.get("seller_name")
        seller_country = lowest_new.get("seller_country")
        buy_link = lowest_new.get("buy_link")
        buy_price = lowest_new.get("buy_price")
        condition = "NEW"
    elif lowest_new_price == 0 and lowest_used_price == 0:
        seller_name = "None"
        seller_country = "None"
        buy_link = "#"
        buy_price = 0.0
        condition = "NONE"
    else:
        if lowest_new_price < lowest_used_price: # type: ignore
            seller_name = lowest_new.get("seller_name")
            seller_country = lowest_new.get("seller_country")
            buy_link = lowest_new.get("buy_link")
            buy_price = lowest_new.get("buy_price")
            condition = "NEW"
        else:
            seller_name = lowest_used.get("seller_name")
            seller_country = lowest_used.get("seller_country")
            buy_link = lowest_used.get("buy_link")
            buy_price = lowest_used.get("buy_price")    
            condition = "USED"  
   # print(f"lowest_new_price: {lowest_new_price}, lowest_used_price: {lowest_used_price}, selected condition: {condition}, buy_price: {buy_price}")
    buyback = best_buyback_price_from_Html(soup)
    buyback_price = safe_float(buyback.get("buyback_price")) if isinstance(buyback, dict) else None
    title = buyback.get("title") if isinstance(buyback, dict) else None
    buyback_link = buyback.get("buyback_link") if isinstance(buyback, dict) else None

    if buyback_price > buy_price: # type: ignore
        is_profitable = True
    else:   
        is_profitable = False
    profit = round(safe_float(buyback_price) - safe_float(buy_price), 2) # type: ignore
    
    return {
        "isbn": isbn,
        "title": title, # type: ignore
        "seller_name": seller_name,
        "seller_country": seller_country,
        "condition": condition,
        "buy_price": buy_price,
        "buyback_price": buyback_price,
        "profit": profit,
        "buy_link": buy_link,
        "buyback_link": buyback_link,
        "is_profitable": is_profitable,
    }


def _fetch_html_playwright_sync(url: str, *, navigation_timeout_ms: int = 90_000) -> str:
    """Sync Playwright fetch for worker threads when the asyncio loop cannot use subprocess."""
    state_path = _bookfinder_storage_state_path()
    ctx_kwargs: dict = {
        "user_agent": DEFAULT_HEADERS["User-Agent"],
        "locale": "en-US",
        "viewport": {"width": 1365, "height": 900},
        "extra_http_headers": {
            "Accept-Language": DEFAULT_HEADERS.get("Accept-Language", "en-US,en;q=0.9"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    }
    if state_path.is_file():
        ctx_kwargs["storage_state"] = str(state_path)
        #logger.info("Sync fetch context from reCAPTCHA storage: %s", state_path)
    else:
        logger.warning(
            "No storage file at %s — fetch may hit reCAPTCHA again. Run pass_captcha first.",
            state_path,
        )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()
        try:
            response = page.goto(url, wait_until="load", timeout=navigation_timeout_ms)
            if response is not None and response.status == 429:
                ra = _retry_after_seconds_from_response(response)
                raise BookFinderRateLimited(
                    f"HTTP 429 Too Many Requests for {url}",
                    retry_after=ra,
                )
            if response is not None and response.status >= 400:
                logger.warning("HTTP %s for %s", response.status, url)
            ready_selector = (
                "[data-csa-c-offerstype], "
                '[data-csa-c-clickouttype="buyback"], '
                "[data-csa-c-condition], "
                "h1"
            )
            try:
                page.wait_for_selector(ready_selector, timeout=20_000)
            except PlaywrightTimeoutError:
                logger.warning("Selectors not ready; returning HTML anyway: %s", url)
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeoutError:
                pass
            time.sleep(1)
            return page.content()
        finally:
            page.close()
            context.close()
            browser.close()


async def _fetch_html_playwright(url: str, *, navigation_timeout_ms: int = 90_000) -> str:
    """
    Open ``url`` in Playwright (async). Uses **one shared BrowserContext** built from the
    reCAPTCHA session file (``storage_state`` written by ``_run_sync_captcha_flow`` on the
    first CAPTCHA page), so ISBN requests reuse the same cookies as that first page.
    """
    if _windows_async_playwright_unsupported():
        global _sync_playwright_fallback_logged
        if not _sync_playwright_fallback_logged:
            _sync_playwright_fallback_logged = True
            logger.warning(
                "Using sync Playwright in worker threads: this asyncio loop cannot spawn subprocess "
                "(common with uvicorn --reload on Windows). Run without --reload or use ProactorEventLoop for shared async browser."
            )
        return await asyncio.to_thread(
            _fetch_html_playwright_sync,
            url,
            navigation_timeout_ms=navigation_timeout_ms,
        )

    browser = await _ensure_browser()
    global _bf_fetch_context

    async with _bf_fetch_context_lock:
        if _bf_fetch_context is None:
            state_path = _bookfinder_storage_state_path()
            ctx_kwargs: dict = {
                "user_agent": DEFAULT_HEADERS["User-Agent"],
                "locale": "en-US",
                "viewport": {"width": 1365, "height": 900},
                "extra_http_headers": {
                    "Accept-Language": DEFAULT_HEADERS.get("Accept-Language", "en-US,en;q=0.9"),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            }
            if state_path.is_file():
                ctx_kwargs["storage_state"] = str(state_path)
                logger.info("Async context from reCAPTCHA storage: %s", state_path)
            else:
                logger.warning(
                    "No storage file at %s — fetch may hit reCAPTCHA again. Run pass_captcha first.",
                    state_path,
                )
            _bf_fetch_context = await browser.new_context(**ctx_kwargs)
        context = _bf_fetch_context

    page = await context.new_page()

    try:
        response = await page.goto(url, wait_until="load", timeout=navigation_timeout_ms)
        if response is not None and response.status == 429:
            ra = _retry_after_seconds_from_response(response)
            raise BookFinderRateLimited(
                f"HTTP 429 Too Many Requests for {url}",
                retry_after=ra,
            )
        if response is not None and response.status >= 400:
            logger.warning("HTTP %s for %s", response.status, url)

        ready_selector = (
            "[data-csa-c-offerstype], "
            '[data-csa-c-clickouttype="buyback"], '
            "[data-csa-c-condition], "
            "h1"
        )
        try:
            await page.wait_for_selector(ready_selector, timeout=45_000)
        except AsyncPlaywrightTimeoutError:
            logger.warning("Selectors not ready; returning HTML anyway: %s", url)

        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except AsyncPlaywrightTimeoutError:
            pass

        await asyncio.sleep(1)
        html = await page.content()
        # if len(html) < 800:
        #     logger.warning("Very short HTML (%s chars) for %s", len(html), url)
        return html
    finally:
        await page.close()


def _run_sync_captcha_flow( start_url: str, *, headless: bool, interactive_prompt: bool,) -> None:
    """
    Sync Playwright + openai_image_numbers. Must run in a worker thread (asyncio.to_thread),
    not on FastAPI's asyncio loop.

    The visible Chromium window **closes when this function returns**: cookies are already
    written to disk (``storage_state``); keeping the GUI open would block the server. ISBN
    scraping then uses a **separate headless** async browser that loads that same session
    from the file (no second visible window unless you change ``HEADLESS`` for async too).

    Env ``BOOKFINDER_CAPTCHA_PAUSE_SECONDS`` (e.g. ``5``): seconds to wait before closing the
    CAPTCHA window so you can inspect the page after solve.
    """
    launch_args: list[str] = [] if headless else ["--start-maximized"]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=launch_args)
        context = browser.new_context(no_viewport=True)
        page = context.new_page()
        try:
            logger.info("reCAPTCHA: first page GET %s", start_url)
            page.goto(start_url, wait_until="load")
            _human_delay(1.0, 2.0)
            try:
                click_amzn_captcha_verify_button(page)
            except PlaywrightTimeoutError:
                logger.info(
                    "No .amzn-captcha-verify-button within timeout; "
                    "page may not show that control."
                )
            run_post_load_captcha_and_screenshot(page)

            state_path = _bookfinder_storage_state_path()
            state_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(state_path))
            logger.info("Saved reCAPTCHA session for async ISBN fetches: %s", state_path)

            pause_raw = os.environ.get("BOOKFINDER_CAPTCHA_PAUSE_SECONDS", "").strip()
            if pause_raw:
                try:
                    pause_sec = float(pause_raw)
                    if pause_sec > 0:
                        logger.info(
                            "Pausing %.1fs before closing CAPTCHA browser (BOOKFINDER_CAPTCHA_PAUSE_SECONDS)",
                            pause_sec,
                        )
                        time.sleep(pause_sec)
                except ValueError:
                    logger.warning("Invalid BOOKFINDER_CAPTCHA_PAUSE_SECONDS=%r", pause_raw)

            if interactive_prompt and not headless:
                print("Close the browser window or press Enter here to exit.")
                try:
                    input()
                except EOFError:
                    pass
        finally:
            context.close()
            browser.close()

async def pass_captcha(isbn: Optional[str] = None, *, force: bool = False) -> None:
    """
    Solve reCAPTCHA on the first BookFinder page (``SEARCH_URL + isbn`` or ``START_URL``),
    save ``storage_state`` to disk, then clear the async fetch context so the next
    ``_fetch_html_playwright`` loads that session.
    """
    global _captcha_warmup_once_done

    warmup_mode = os.environ.get("BOOKFINDER_CAPTCHA_WARMUP", "once").lower().strip()
    if warmup_mode == "never" and not force:
        return

    if isbn and isbn.strip():
        load_url = SEARCH_URL + isbn.strip()
    else:
        load_url = os.environ.get("START_URL", DEFAULT_URL)

    headless = os.environ.get("HEADLESS", "").lower() in ("1", "true", "yes")
    interactive_prompt = os.environ.get("CAPTCHA_INTERACTIVE", "").lower() in ("1", "true", "yes")

    should_run = force
    if not force:
        if warmup_mode == "always":
            should_run = True
        elif warmup_mode == "once":
            async with _captcha_warmup_lock:
                if not _captcha_warmup_once_done:
                    _captcha_warmup_once_done = True
                    should_run = True

    if not should_run:
        return
    try:
        await asyncio.to_thread( _run_sync_captcha_flow, load_url, headless=headless, interactive_prompt=interactive_prompt, )
    except Exception:
        logger.exception("CAPTCHA warmup failed; continuing")
    finally:
        await _close_bookfinder_fetch_context()

# Main scraping function with retries and backoff
async def scrape_bookfinder(
    isbn: str,
    filters: dict,
    *,
    backoff_base: float = 1.5,
    max_retries: Optional[int] = None,
) -> dict:
    isbn = isbn.strip()
    fetch_url = SEARCH_URL + isbn
    if max_retries is None:
        max_retries = int(os.environ.get("BOOKFINDER_MAX_RETRIES", "10"))
    base_429 = float(os.environ.get("BOOKFINDER_429_BACKOFF_BASE", "10"))
    cap_429 = float(os.environ.get("BOOKFINDER_429_BACKOFF_MAX", "10"))
    logger.info("Scraping BookFinder URL: %s", fetch_url)
    attempt = 0
    try:
        while attempt <= max_retries:
            try:
                html = await _fetch_html_playwright(fetch_url)
                # If BookFinder challenge page appears, run CAPTCHA flow on this ISBN URL,
                # refresh async context, and fetch again using saved storage_state.
                if "confirm you are human" in html.lower():
                    logger.info("reCAPTCHA challenge detected for %s; forcing pass_captcha", isbn)
                    await pass_captcha(isbn, force=True)
                    await asyncio.sleep(random.uniform(2.0, 3.5))
                    html = await _fetch_html_playwright(fetch_url)
                return await asyncio.to_thread(parse_search_html, html, isbn, filters)
            except BookFinderRateLimited as e:
                wait = random.uniform(4.5, 5.8)
                logger.warning(
                    "HTTP 429 rate limited for %s — sleeping %.0fs before retry (attempt %s/%s)",
                    isbn,
                    wait,
                    attempt + 1,
                    max_retries + 1,
                )
                time.sleep(wait)
                attempt += 1
            except Exception as e:
                logger.warning(
                    "Playwright fetch attempt %s for %s failed: %s",
                    attempt + 1,
                    isbn,
                    e,
                )
                wait = backoff_base ** attempt + random.random()
                await asyncio.sleep(wait)
                attempt += 1
        return {}
    except Exception as e:
        logger.error("Error scraping ISBN %s: %s", isbn, e)
        wait = backoff_base ** attempt + random.random()
        await asyncio.sleep(wait)
        return {}
    
# Send email alert function
async def send_email_alert(recipient: str, finds):
    """
    Send email alert for profitable finds (via Gmail SMTP or other server)
    """
    try:
        SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        SMTP_PORT = os.environ.get('SMTP_PORT', '587')
        SENDER_EMAIL = os.environ.get('SENDER_EMAIL')
        SENDER_PASSWORD = os.environ.get('SENDER_PASSWORD')

        #print(f"SMTP_SERVER: {SMTP_SERVER}, SMTP_PORT: {SMTP_PORT}, SENDER_EMAIL: {SENDER_EMAIL}")

        if not all([SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD]):
            logger.warning("Missing SMTP configuration")
            return

        try:
            smtp_port = int(SMTP_PORT)
        except ValueError:
            logger.warning("SMTP_PORT must be a valid integer")
            return

        # ✅ Build HTML table manually
        rows_html = ""
        for f in finds:
            rows_html += f"""
            <tr>
                <td style="text-align:center;">{finds.index(f) + 1}</td>
                <td style="text-align:center;">{f.get("isbn")}</td>
                <td style="text-align:center;">{f.get("title", "")}</td>
                <td style="text-align:center;">${f.get("buy_price", 0.0):.2f}</td>
                <td style="text-align:center;">${f.get("buyback_price", 0.0):.2f}</td>
                <td style="text-align:center;"><strong>${f.get("profit", 0.0):.2f}</strong></td>
                <td style="text-align:center;">{f.get("condition", "")}</td>
                <td style="text-align:center;">{f.get("seller_name", "")}</td>
                <td style="text-align:center;">{f.get("seller_country", "")}</td>
                <td style="text-align:center;"><a href="{f.get("buy_link", "#")}" target="_blank">View Buy Price</a></td>
                <td style="text-align:center;"><a href="{f.get("buyback_link", "#")}" target="_blank">View Buyback Price</a></td>
            </tr>
            """

        html_content = f"""
        <body>
            <p style="font-size: 16px; font-weight: bold; text-align: center;">
                📘 Profitable Book Arbitrage Opportunity Found!
            </p>
            <table border="1" cellspacing="0" cellpadding="8" style="border-collapse: collapse; width: 100%; max-width: 900px; margin: 0 auto; text-align: center;">
                <thead style="background-color: #f2f2f2;">
                    <tr>
                        <th style="text-align:center;">No</th>
                        <th style="text-align:center;">ISBN</th>
                        <th style="text-align:center;">Title</th>
                        <th style="text-align:center;">Buy Price</th>
                        <th style="text-align:center;">Buyback Price</th>
                        <th style="text-align:center;">Profit</th>
                        <th style="text-align:center;">Condition</th>
                        <th style="text-align:center;">Seller</th>
                        <th style="text-align:center;">Country</th>
                        <th style="text-align:center;">Buy Link</th>
                        <th style="text-align:center;">Buyback Link</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </body>
        """

        # SENDER_EMAIL has been validated above; cast to str so type-checkers know it's non-None
        sender_email = str(SENDER_EMAIL)
        sender_password = str(SENDER_PASSWORD)

        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Subject"] = "📘 Profitable Book Arbitrage Opportunity!"
        msg.attach(MIMEText(html_content, "html"))
        with smtplib.SMTP(SMTP_SERVER, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            logger.info(f"✅ Email sent successfully to {recipient}")

    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")

