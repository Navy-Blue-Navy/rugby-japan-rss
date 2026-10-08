import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from email.utils import format_datetime, parsedate_to_datetime
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
import hashlib
import os
import re

URL = "https://www.rugby-japan.jp/news/"
OUTPUT = "rugby_japan.xml"

JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

DATE_PATTERN = re.compile(
    r"(20\d{2})[./年]\s*(\d{1,2})[./月]\s*(\d{1,2})"
)


def make_guid(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def get_old_items():
    old = {}

    if not os.path.exists(OUTPUT):
        return old

    try:
        root = ET.parse(OUTPUT).getroot()

        for item in root.findall("./channel/item"):
            guid = item.findtext("guid")

            if guid:
                old[guid] = {
                    "title": item.findtext("title") or "",
                    "link": item.findtext("link") or "",
                    "description": item.findtext("description") or "",
                    "pubDate": item.findtext("pubDate") or "",
                }

    except Exception:
        pass

    return old


def clean_title(text):
    text = " ".join(text.split())

    # 日付以降を削除
    m = DATE_PATTERN.search(text)

    if m:
        text = text[:m.start()].strip()

    return text


response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

print(
    "一覧ページ HTTP:",
    response.status_code
)

response.raise_for_status()

soup = BeautifulSoup(
    response.text,
    "html.parser"
)

items = []
seen = set()

for a in soup.find_all("a", href=True):

    href = a.get("href", "")
    article_url = urljoin(URL, href)

    # 個別ニュース記事だけ
    if not re.fullmatch(
        r"https://www\.rugby-japan\.jp/news/\d+/?",
        article_url
    ):
        continue

    if article_url in seen:
        continue

    # -------------------------
    # タイトル取得
    # -------------------------

    title = " ".join(a.stripped_strings).strip()

    if not title:
        continue

    title = clean_title(title)

    if not title:
        continue

    # -------------------------
    # 記事カード周辺から日付取得
    # -------------------------

    parent = a
    date_match = None

    for _ in range(8):

        if parent is None:
            break

        block_text = " ".join(
            parent.stripped_strings
        )

        date_match = DATE_PATTERN.search(
            block_text
        )

        if date_match:
            break

        parent = parent.parent

    if not date_match:
        print(
            "日付取得失敗:",
            title,
            article_url
        )
        continue

    year, month, day = map(
        int,
        date_match.groups()
    )

    dt = datetime(
        year,
        month,
        day,
        12,
        0,
        0,
        tzinfo=JST
    )

    seen.add(article_url)

    items.append({
        "title": title,
        "link": article_url,
        "description":
            "日本ラグビーフットボール協会 ニュース",
        "pubDate":
            format_datetime(dt),
        "guid":
            make_guid(article_url),
        "sort_date":
            dt,
    })


items.sort(
    key=lambda x: x["sort_date"],
    reverse=True
)

# -------------------------
# 既存RSSを保持
# -------------------------

old_items = get_old_items()
all_items = dict(old_items)

for item in items:

    all_items[
        item["guid"]
    ] = {
        "title":
            item["title"],
        "link":
            item["link"],
        "description":
            item["description"],
        "pubDate":
            item["pubDate"],
    }


def parse_date(value):

    try:
        return parsedate_to_datetime(
            value
        )

    except Exception:
        return datetime(
            1970,
            1,
            1,
            tzinfo=timezone.utc
        )


sorted_items = sorted(
    all_items.items(),
    key=lambda x:
        parse_date(
            x[1]["pubDate"]
        ),
    reverse=True
)[:300]

# -------------------------
# RSS生成
# -------------------------

rss = ET.Element(
    "rss",
    version="2.0"
)

channel = ET.SubElement(
    rss,
    "channel"
)

ET.SubElement(
    channel,
    "title"
).text = (
    "日本ラグビーフットボール協会 ニュース"
)

ET.SubElement(
    channel,
    "link"
).text = URL

ET.SubElement(
    channel,
    "description"
).text = (
    "日本ラグビーフットボール協会"
    "「ニュース・すべて」の新着情報"
)

ET.SubElement(
    channel,
    "language"
).text = "ja"

for guid, data in sorted_items:

    item = ET.SubElement(
        channel,
        "item"
    )

    ET.SubElement(
        item,
        "title"
    ).text = data["title"]

    ET.SubElement(
        item,
        "link"
    ).text = data["link"]

    ET.SubElement(
        item,
        "description"
    ).text = data["description"]

    ET.SubElement(
        item,
        "pubDate"
    ).text = data["pubDate"]

    guid_el = ET.SubElement(
        item,
        "guid",
        isPermaLink="false"
    )

    guid_el.text = guid


tree = ET.ElementTree(rss)

ET.indent(
    tree,
    space="  "
)

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)

# -------------------------
# 結果表示
# -------------------------

print()
print("RSS作成成功")
print(
    "今回取得:",
    len(items),
    "件"
)
print(
    "RSS保存件数:",
    len(sorted_items),
    "件"
)

print()
print("取得記事:")

for i, item in enumerate(
    items,
    1
):

    print()
    print(
        f"[{i}] {item['title']}"
    )
    print(
        "    ",
        item["pubDate"]
    )
    print(
        "    ",
        item["link"]
    )
