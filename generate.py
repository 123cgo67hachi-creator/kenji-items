#!/usr/bin/env python3
import json, urllib.request, os, re
from datetime import datetime, timezone, timedelta

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DB_ID = "fd7b3071-f92a-46d6-8cf4-0eab85108bf9"

def query_notion():
    all_results = []
    cursor = None
    while True:
        body = {
            "filter": {"property": "ステータス", "select": {"equals": "投稿済み"}},
            "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
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
        all_results.extend(data["results"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return all_results

def parse_products(results):
    products = []
    index = {}
    for r in results:
        props = r["properties"]
        name_arr = props.get("商品名", {}).get("title", [])
        raw = name_arr[0].get("plain_text", "") if name_arr else ""
        if not raw:
            continue
        display = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]$', '', raw).strip()
        rakuten = props.get("楽天リンク", {}).get("url", "") or ""
        thumb = props.get("サムネURL", {}).get("url", "") or ""
        if display in index:
            # 同名（①②）は1枚にまとめる。リンク・画像は入っている方を採用
            p = index[display]
            p["rakuten_url"] = p["rakuten_url"] or rakuten
            p["thumb_url"] = p["thumb_url"] or thumb
            continue
        p = {
            "name": display,
            "rakuten_url": rakuten,
            "thumb_url": thumb,
            "date": r.get("created_time", "")[:10],
        }
        index[display] = p
        products.append(p)
    return products

def generate_html(products):
    products_json = json.dumps(products, ensure_ascii=False)
    jst = timezone(timedelta(hours=9))
    updated = datetime.now(jst).strftime("%Y-%m-%d %H:%M")

    return f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>けんじのオススメアイテム</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
  background: #f5f5f7;
  color: #1d1d1f;
  min-height: 100vh;
}}
.header {{
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  color: white;
  padding: 2rem 1rem 1.5rem;
  text-align: center;
}}
.header h1 {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 0.3rem; }}
.header p {{ font-size: 0.8rem; opacity: 0.7; }}
.pr-badge {{
  display: inline-block;
  background: rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.9);
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 4px;
  margin-top: 0.5rem;
}}
.search-container {{
  padding: 1rem;
  position: sticky;
  top: 0;
  z-index: 10;
  background: #f5f5f7;
}}
.search-input {{
  width: 100%;
  padding: 0.75rem 1rem 0.75rem 2.5rem;
  border: none;
  border-radius: 12px;
  font-size: 1rem;
  background: white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  outline: none;
  transition: box-shadow 0.2s;
}}
.search-input:focus {{ box-shadow: 0 2px 16px rgba(0,0,0,0.15); }}
.search-icon {{
  position: absolute;
  left: 1.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: #999;
  font-size: 1rem;
}}
.count {{ text-align: center; font-size: 0.75rem; color: #888; padding: 0.25rem 0 0.5rem; }}
.grid {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  padding: 0 1rem 2rem;
}}
.card {{
  background: white;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  transition: transform 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
}}
.card:active {{ transform: scale(0.97); }}
.card-thumb {{
  width: 100%;
  aspect-ratio: 1;
  background: linear-gradient(135deg, #e8e8ed 0%, #d2d2d7 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 2rem;
  overflow: hidden;
}}
.card-thumb img {{ width: 100%; height: 100%; object-fit: cover; }}
.card-body {{
  padding: 0.6rem 0.75rem;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}}
.card-name {{
  font-size: 0.8rem;
  font-weight: 600;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.card-date {{ font-size: 0.65rem; color: #999; }}
.card-btn {{
  display: block;
  text-align: center;
  padding: 0.5rem;
  background: #bf0000;
  color: white;
  text-decoration: none;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 8px;
  margin-top: auto;
  transition: background 0.15s;
}}
.card-btn:hover {{ background: #a00; }}
.card-btn.disabled {{ background: #ccc; pointer-events: none; }}
.no-results {{ grid-column: 1 / -1; text-align: center; padding: 3rem 1rem; color: #999; }}
.footer {{
  text-align: center;
  padding: 1.5rem;
  font-size: 0.65rem;
  color: #999;
  border-top: 1px solid #e5e5ea;
  background: white;
}}
@media (min-width: 480px) {{ .grid {{ grid-template-columns: repeat(3, 1fr); }} }}
@media (min-width: 768px) {{
  .grid {{ grid-template-columns: repeat(4, 1fr); gap: 1rem; padding: 0 2rem 2rem; }}
  .search-container {{ padding: 1rem 2rem; }}
}}
</style>
</head>
<body>
<div class="header">
  <h1>けんじのオススメアイテム</h1>
  <p>TikTokで紹介した商品まとめ</p>
  <span class="pr-badge">広告・PR</span>
</div>
<div class="search-container" style="position:sticky; top:0;">
  <span class="search-icon">&#128269;</span>
  <input type="text" class="search-input" placeholder="商品を検索..." id="searchInput">
</div>
<div class="count" id="countText"></div>
<div class="grid" id="productGrid"></div>
<div class="footer">
  <p>最終更新: {updated}</p>
  <p style="margin-top:4px;">※ 価格・在庫は変動する場合があります。</p>
</div>
<script>
const products = {products_json};
function renderProducts(filter) {{
  const grid = document.getElementById('productGrid');
  const countEl = document.getElementById('countText');
  const q = (filter || '').toLowerCase();
  const filtered = q ? products.filter(p => p.name.toLowerCase().includes(q)) : products;
  countEl.textContent = filtered.length + ' アイテム';
  if (filtered.length === 0) {{
    grid.innerHTML = '<div class="no-results">該当する商品がありません</div>';
    return;
  }}
  grid.innerHTML = filtered.map(p => {{
    const thumbHtml = p.thumb_url
      ? '<img src="' + p.thumb_url + '" alt="' + p.name + '" loading="lazy">'
      : '<span>&#128230;</span>';
    const btnClass = p.rakuten_url ? 'card-btn' : 'card-btn disabled';
    const btnHref = p.rakuten_url || '#';
    const btnText = p.rakuten_url ? '楽天で見る' : '準備中';
    return '<div class="card"><div class="card-thumb">' + thumbHtml + '</div><div class="card-body">' +
      '<div class="card-name">' + p.name + '</div><div class="card-date">' + p.date + '</div>' +
      '<a href="' + btnHref + '" target="_blank" rel="noopener noreferrer" class="' + btnClass + '">' + btnText + '</a>' +
      '</div></div>';
  }}).join('');
}}
document.getElementById('searchInput').addEventListener('input', function() {{ renderProducts(this.value); }});
renderProducts('');
</script>
</body>
</html>'''

if __name__ == "__main__":
    results = query_notion()
    products = parse_products(results)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(generate_html(products))
    print(f"Generated: {len(products)} products")
