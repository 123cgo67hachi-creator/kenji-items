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

def clean_name(raw):
    # 「冷感ポンチョ ① 」のように①の後ろに空白があると末尾判定に失敗するため、
    # 先に前後の空白を落としてから①〜⑩を外す（update_notion.py と必ず同じ規則にする）
    return re.sub(r'\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*$', '', (raw or "").strip()).strip()

def parse_products(results):
    products = []
    index = {}
    for r in results:
        props = r["properties"]
        name_arr = props.get("商品名", {}).get("title", [])
        raw = name_arr[0].get("plain_text", "") if name_arr else ""
        if not raw:
            continue
        display = clean_name(raw)
        rakuten = props.get("楽天リンク", {}).get("url", "") or ""
        tiktok = props.get("TikTokリンク", {}).get("url", "") or ""
        thumb = props.get("サムネURL", {}).get("url", "") or ""
        # 「表示順」は旦那様がadminから手で付ける固定順。小さいほど前。未設定はNone
        order = props.get("表示順", {}).get("number", None)
        # 並べ替えの基準日は投稿の実態に近い「動画納品日」。無ければ案件作成日で代用する
        deliv = (props.get("動画納品日", {}).get("date") or {}).get("start", "") or ""
        date = deliv[:10] or r.get("created_time", "")[:10]
        if display in index:
            # 同名（①②）は1枚にまとめる。リンク・画像・表示順は入っている方を採用
            p = index[display]
            p["rakuten_url"] = p["rakuten_url"] or rakuten
            p["tiktok_url"] = p["tiktok_url"] or tiktok
            p["thumb_url"] = p["thumb_url"] or thumb
            if p["order"] is None:
                p["order"] = order
            if date > p["date"]:
                p["date"] = date
            continue
        p = {
            "name": display,
            "rakuten_url": rakuten,
            "tiktok_url": tiktok,
            "thumb_url": thumb,
            "date": date,
            "order": order,
        }
        index[display] = p
        products.append(p)

    # 既定（おすすめ順）の並び。優先度は上から順に：
    #   1. 「表示順」が入っているものを最優先（旦那様がadminで固定した順番）
    #   2. 買えるもの（リンクあり）を前に
    #   3. その中で新しい順
    # 案件ページは毎朝の自動処理でも更新日が動くため、Notionの更新日順は使わない。
    def sort_key(p):
        has_order = p["order"] is not None
        return (
            0 if has_order else 1,
            p["order"] if has_order else 0,
            0 if (p["rakuten_url"] or p["tiktok_url"]) else 1,
            # 日付は降順にしたいので文字列を反転比較する代わりに負のキーを作る
            [-ord(c) for c in p["date"]],
            p["name"],
        )
    products.sort(key=sort_key)
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
.sortbar {{
  display: flex;
  gap: 0.4rem;
  overflow-x: auto;
  padding: 0 1rem 0.5rem;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}}
.sortbar::-webkit-scrollbar {{ display: none; }}
.sortbar button {{
  flex: 0 0 auto;
  border: 1px solid #d2d2d7;
  background: #fff;
  color: #444;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  cursor: pointer;
  font-family: inherit;
}}
.sortbar button[aria-pressed="true"] {{
  background: #1d1d1f;
  border-color: #1d1d1f;
  color: #fff;
}}
@media (min-width: 768px) {{ .sortbar {{ padding: 0 2rem 0.5rem; }} }}
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
.card-links {{
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}}
.card-btn {{
  display: block;
  text-align: center;
  padding: 0.5rem;
  text-decoration: none;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 8px;
  border: 1.5px solid transparent;
  transition: opacity 0.15s;
}}
.card-btn:active {{ opacity: 0.7; }}
/* TikTokショップ＝主導線。塗りつぶしの黒で目立たせる */
.btn-tiktok {{ background: #000; color: #fff; }}
/* 楽天＝副導線。枠線だけにして一段控えめに見せる */
.btn-rakuten {{ background: #fff; color: #bf0000; border-color: #bf0000; }}
.btn-note {{
  font-size: 0.6rem;
  color: #888;
  text-align: center;
  line-height: 1.3;
  margin-top: -0.15rem;
}}
.card-btn.disabled {{
  background: #f0f0f2;
  color: #aaa;
  pointer-events: none;
}}
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
<div class="sortbar" id="sortBar">
  <button data-sort="recommended" aria-pressed="true">おすすめ順</button>
  <button data-sort="newest" aria-pressed="false">新しい順</button>
  <button data-sort="oldest" aria-pressed="false">古い順</button>
  <button data-sort="name" aria-pressed="false">名前順</button>
  <button data-sort="buyable" aria-pressed="false">買えるものだけ</button>
</div>
<div class="count" id="countText"></div>
<div class="grid" id="productGrid"></div>
<div class="footer">
  <p>最終更新: {updated}</p>
  <p style="margin-top:4px;">※ 価格・在庫は変動する場合があります。</p>
</div>
<script>
const products = {products_json};
// products は生成時点で「おすすめ順」に並んでいる。その並びを既定として保持する。
const RECOMMENDED = products.slice();
let currentSort = 'recommended';
const hasLink = p => !!(p.tiktok_url || p.rakuten_url);

function applySort(list) {{
  const a = list.slice();
  if (currentSort === 'newest')  return a.sort((x, y) => (y.date || '').localeCompare(x.date || ''));
  if (currentSort === 'oldest')  return a.sort((x, y) => (x.date || '').localeCompare(y.date || ''));
  if (currentSort === 'name')    return a.sort((x, y) => x.name.localeCompare(y.name, 'ja'));
  if (currentSort === 'buyable') return a.filter(hasLink);
  return a; // おすすめ順＝生成時の並びのまま
}}

function renderProducts(filter) {{
  const grid = document.getElementById('productGrid');
  const countEl = document.getElementById('countText');
  const q = (filter || '').toLowerCase();
  const base = currentSort === 'recommended' ? RECOMMENDED : applySort(RECOMMENDED);
  const filtered = q ? base.filter(p => p.name.toLowerCase().includes(q)) : base;
  countEl.textContent = filtered.length + ' アイテム';
  if (filtered.length === 0) {{
    grid.innerHTML = '<div class="no-results">該当する商品がありません</div>';
    return;
  }}
  grid.innerHTML = filtered.map(p => {{
    const thumbHtml = p.thumb_url
      ? '<img src="' + p.thumb_url + '" alt="' + p.name + '" loading="lazy">'
      : '<span>&#128230;</span>';
    // リンクが無い方のボタンは出さない。両方無いときだけ「準備中」を出す
    let linksHtml = '';
    if (p.tiktok_url) {{
      linksHtml += '<a href="' + p.tiktok_url + '" target="_blank" rel="noopener noreferrer nofollow" class="card-btn btn-tiktok">TikTokで見る</a>' +
        '<div class="btn-note">クーポンが出ることがあります</div>';
    }}
    if (p.rakuten_url) {{
      linksHtml += '<a href="' + p.rakuten_url + '" target="_blank" rel="noopener noreferrer nofollow" class="card-btn btn-rakuten">楽天で見る</a>';
    }}
    if (!linksHtml) {{
      linksHtml = '<span class="card-btn disabled">準備中</span>';
    }}
    return '<div class="card"><div class="card-thumb">' + thumbHtml + '</div><div class="card-body">' +
      '<div class="card-name">' + p.name + '</div><div class="card-date">' + p.date + '</div>' +
      '<div class="card-links">' + linksHtml + '</div>' +
      '</div></div>';
  }}).join('');
}}
document.getElementById('searchInput').addEventListener('input', function() {{ renderProducts(this.value); }});
document.getElementById('sortBar').addEventListener('click', function(e) {{
  const btn = e.target.closest('button[data-sort]');
  if (!btn) return;
  currentSort = btn.dataset.sort;
  this.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
  renderProducts(document.getElementById('searchInput').value);
}});
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
