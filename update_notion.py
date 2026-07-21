#!/usr/bin/env python3
import json, urllib.request, os, re

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = "fd7b3071-f92a-46d6-8cf4-0eab85108bf9"
PRODUCT_NAME = os.environ.get("PRODUCT_NAME", "")
RAKUTEN_URL = os.environ.get("RAKUTEN_URL", "")
IMAGE_FILENAME = os.environ.get("IMAGE_FILENAME", "")
PAGES_BASE = "https://123cgo67hachi-creator.github.io/kenji-items"

def find_pages_by_name(name):
    clean = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]$', '', name).strip()
    matches = []
    cursor = None
    while True:
        body = {
            "filter": {"property": "ステータス", "select": {"equals": "投稿済み"}},
            "page_size": 100
        }
        if cursor:
            body["start_cursor"] = cursor
        req = urllib.request.Request(
            f"https://api.notion.com/v1/databases/{DB_ID}/query",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        for r in data["results"]:
            title_arr = r["properties"].get("商品名", {}).get("title", [])
            title = title_arr[0].get("plain_text", "") if title_arr else ""
            title_clean = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]$', '', title).strip()
            if title_clean == clean:
                matches.append(r["id"])

        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return matches

def update_page(page_id, rakuten_url=None, thumb_url=None):
    props = {}
    if rakuten_url:
        props["楽天リンク"] = {"url": rakuten_url}
    if thumb_url:
        props["サムネURL"] = {"url": thumb_url}
    if not props:
        return
    body = {"properties": props}
    req = urllib.request.Request(
        f"https://api.notion.com/v1/pages/{page_id}",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        },
        method="PATCH"
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()

if __name__ == "__main__":
    if not PRODUCT_NAME:
        print("No product name provided, skipping")
        exit(0)

    thumb_url = f"{PAGES_BASE}/images/{IMAGE_FILENAME}" if IMAGE_FILENAME else None
    pages = find_pages_by_name(PRODUCT_NAME)
    print(f"Found {len(pages)} pages for '{PRODUCT_NAME}'")
    if not pages:
        # 無言で成功扱いにすると気づけないので、ここで落とす
        print(f"ERROR: ステータス=投稿済み に '{PRODUCT_NAME}' が見つかりません")
        exit(1)
    for pid in pages:
        update_page(pid, RAKUTEN_URL or None, thumb_url)
        print(f"  Updated: {pid}")
