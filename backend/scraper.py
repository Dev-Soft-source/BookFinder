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
import requests
import time
import random
import re

logger = logging.getLogger(__name__)

SEARCH_URL = "https://bookfinder.com/isbn/"  # or the exact endpoint you discover
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

# Main scraping function with retries and backoff
async def scrape_bookfinder(isbn: str, filters: dict, *, backoff_base=1.5, max_retries=3) -> dict:
    """
    Scrape BookFinder.com for a given ISBN
    Returns dict with pricing data or None if no profitable opportunity
    """
        
    try:
        session = requests.Session()
        attempt = 0
        while attempt <= max_retries:
            try:
                url = SEARCH_URL + isbn
                resp = session.get(url, headers=DEFAULT_HEADERS, timeout=20)
                # await asyncio.sleep(1)
                if resp.status_code == 200:
                    return parse_search_html(resp.text, isbn, filters)
                elif resp.status_code in (429, 503):
                    # rate-limited or service unavailable: back off
                    wait = backoff_base ** attempt + random.random()
                    time.sleep(wait)
                    attempt += 1
                else:
                    # unexpected status
                    resp.raise_for_status()
            except requests.RequestException as e:
                wait = backoff_base ** attempt + random.random()
                time.sleep(wait)
                attempt += 1
        return {}
    
    except Exception as e:
        logger.error(f"Error scraping ISBN {isbn}: {str(e)}")
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

        print(f"SMTP_SERVER: {SMTP_SERVER}, SMTP_PORT: {SMTP_PORT}, SENDER_EMAIL: {SENDER_EMAIL}")

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

