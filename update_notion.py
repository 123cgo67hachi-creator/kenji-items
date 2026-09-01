#!/usr/bin/env python3
import json, urllib.request, os, re

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = "fd7b3071-f92a-46d6-8cf4-0eab85108bf9"
PRODUCT_NAME = os.environ.get("PRODUCT_NAME", "")
RAKUTEN_URL = os.environ.get("RAKUTEN_URL", "")
TIKTOK_URL = os.environ.get("TIKTOK_URL", "")
IMAGE_FILENAME = os.environ.get("IMAGE_FILENAME", "")
# 表示順は旦那様がadminで付ける手動の並び順。空文字なら触らず、"clear"で解除する
DISPLAY_ORDER = os.environ.get("DISPLAY_ORDER", "")
# カタログ表示の切り替え。"hide"で隠す、"show"で戻す。空なら触らない
VISIBILITY = os.environ.get("VISIBILITY", "")
PAGES_BASE = "https://123cgo67hachi-creator.github.io/kenji-items"

def clean_name(raw):
    # 「冷感ポンチョ ① 」のように①の後ろに空白があると末尾判定に失敗するため、
    # 先に前後の空白を落としてから①〜⑩を外す（generate.py と必ず同じ規則にする）
    return re.sub(r'\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*$', '', (raw or "").strip()).strip()

def find_pages_by_name(name):
    clean = clean_name(name)
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
            title_clean = clean_name(title)
            if title_clean == clean:
                matches.append(r["id"])

        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return matches

def update_page(page_id, rakuten_url=None, tiktok_url=None, thumb_url=None, display_order="", visibility=""):
    props = {}
    if visibility in ("hide", "show"):
        props["カタログ非表示"] = {"checkbox": visibility == "hide"}
    if display_order:
        # "clear" は手動の並び順をやめて自動（おすすめ順）に戻す指示
        props["表示順"] = {"number": None} if display_order == "clear" else {"number": float(display_order)}
    if rakuten_url:
        props["楽天リンク"] = {"url": rakuten_url}
    if tiktok_url:
        props["TikTokリンク"] = {"url": tiktok_url}
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
        update_page(pid, RAKUTEN_URL or None, TIKTOK_URL or None, thumb_url, DISPLAY_ORDER, VISIBILITY)
        print(f"  Updated: {pid}")
