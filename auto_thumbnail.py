#!/usr/bin/env python3
"""投稿済みなのに画像が無い商品へ、SSDの自前素材から自動でカタログ画像を入れる。

無人で走らせるため判断はすべてこのスクリプト内で完結させる（LLMに判断させない）。

守るルール:
  - 人の素顔が写ったコマは使わない。キツネ面はOK
    （Haar分類器は仮面に反応しないので、素顔だけを機械的に弾ける）
  - 参考動画（他人のTikTok動画）は絶対に使わない。自前で撮った素材だけを使う
  - 画像は1:1・800pxで書き出し、NotionのサムネURLへ反映する
"""
import os, re, sys, json, shutil, subprocess, tempfile, unicodedata, urllib.parse, urllib.request

import cv2

REPO = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(REPO, "images")
SSD_ROOT = "/Volumes/SSD-PHPU3A/編集用動画/検証し太郎"
PAGES_BASE = "https://123cgo67hachi-creator.github.io/kenji-items"
DB_ID = "fd7b3071-f92a-46d6-8cf4-0eab85108bf9"
def _load_secrets():
    """~/.config/amagi/secrets.env を自前で読む。
    無人タスクを「1コマンド実行だけ」に保つため、シェル側で連結しない
    （&&で繋ぐと許可リストの前方一致から外れて実行が止まる）。"""
    path = os.path.expanduser("~/.config/amagi/secrets.env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_secrets()
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")

VIDEO_EXT = (".mov", ".mp4", ".m4v")
# 納品物・参考動画は他人の手が入った素材なので触らない
SKIP_DIRS = {"納品物", "参考動画・商品特徴", "台本"}
# 参考動画としてダウンロードしたファイルの命名パターン（他人の動画＝使用禁止）
BORROWED = re.compile(r"(download|参考|snaptik|ssstik|ダウンロード|^\d{15,}\.)", re.I)
MIN_BYTES = 2_000_000

_cd = cv2.data.haarcascades
_front = cv2.CascadeClassifier(os.path.join(_cd, "haarcascade_frontalface_alt2.xml"))
_prof = cv2.CascadeClassifier(os.path.join(_cd, "haarcascade_profileface.xml"))


# ---------- Notion ----------

def _notion(method, url, body=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def clean_name(raw):
    return re.sub(r"\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*$", "", (raw or "").strip()).strip()


def safe_filename(name):
    n = unicodedata.normalize("NFC", name)
    return re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠ー①-⑩]+", "_", n).strip("_")[:60]


def fetch_targets():
    """ステータス=投稿済み かつ サムネURLが空 の商品を返す。"""
    rows, cursor = {}, None
    while True:
        body = {"filter": {"property": "ステータス", "select": {"equals": "投稿済み"}}, "page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        d = _notion("POST", f"https://api.notion.com/v1/databases/{DB_ID}/query", body)
        for r in d["results"]:
            props = r["properties"]
            title = props.get("商品名", {}).get("title", [])
            raw = title[0].get("plain_text", "") if title else ""
            if not raw:
                continue
            name = clean_name(raw)
            thumb = props.get("サムネURL", {}).get("url") or ""
            ssd = "".join(x.get("plain_text", "") for x in props.get("SSDフォルダ名", {}).get("rich_text", [])).strip()
            hidden = bool(props.get("カタログ非表示", {}).get("checkbox", False))
            e = rows.setdefault(name, {"name": name, "thumb": "", "ssd": "", "hidden": False, "ids": []})
            e["ids"].append(r["id"])
            e["thumb"] = e["thumb"] or thumb
            e["ssd"] = e["ssd"] or ssd
            e["hidden"] = e["hidden"] or hidden
        if not d.get("has_more"):
            break
        cursor = d["next_cursor"]
    # カタログに出さないものへ画像を作っても意味がないので除く
    return [v for v in rows.values() if not v["thumb"] and not v["hidden"]]


def set_thumb(page_ids, filename):
    url = f"{PAGES_BASE}/images/{urllib.parse.quote(filename)}"
    for pid in page_ids:
        _notion("PATCH", f"https://api.notion.com/v1/pages/{pid}", {"properties": {"サムネURL": {"url": url}}})


# ---------- 素材探し ----------

def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[\s　・ー（）()\[\]【】,、。/／①②③④⑤⑥⑦⑧⑨⑩]", "", s)


def find_folder(item, dirs):
    if item["ssd"] and os.path.isdir(os.path.join(SSD_ROOT, item["ssd"])):
        return item["ssd"]
    n = norm(item["name"])
    table = {norm(d): d for d in dirs}
    if n in table:
        return table[n]
    for k, v in table.items():
        if n and (n in k or k in n):
            return v
    return None


def collect_videos(folder):
    out = []
    root_dir = os.path.join(SSD_ROOT, folder)
    for root, subdirs, files in os.walk(root_dir):
        subdirs[:] = [d for d in subdirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if not f.lower().endswith(VIDEO_EXT) or f.startswith("."):
                continue
            if BORROWED.search(f):          # 他人の動画は使わない
                continue
            p = os.path.join(root, f)
            try:
                if os.path.getsize(p) >= MIN_BYTES:
                    out.append(p)
            except OSError:
                pass
    out.sort()
    return out


# ---------- コマ選び ----------

def has_bare_face(bgr):
    h, w = bgr.shape[:2]
    s = 360 / max(h, w)
    im = cv2.resize(bgr, (int(w * s), int(h * s)))
    g = cv2.equalizeHist(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    if len(_front.detectMultiScale(g, 1.15, 6, minSize=(40, 40))):
        return True
    if len(_prof.detectMultiScale(g, 1.15, 6, minSize=(40, 40))):
        return True
    if len(_prof.detectMultiScale(cv2.flip(g, 1), 1.15, 6, minSize=(40, 40))):
        return True
    return False


def quality(bgr):
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(g, (320, max(1, int(320 * g.shape[0] / g.shape[1]))))
    sharp = cv2.Laplacian(small, cv2.CV_64F).var()   # ピント
    expo = 1.0 - abs(small.mean() - 128) / 128.0     # 明るさの偏り
    detail = small.std() / 64.0                      # のっぺり具合（壁だけのコマを落とす）
    return sharp * max(expo, 0.05) * max(detail, 0.05)


def duration(path):
    try:
        o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30).stdout.strip()
        return float(o)
    except Exception:
        return 0.0


def best_frame(videos, sample_videos=14, per_video=2):
    """素顔なしで一番写りの良いコマを1枚選び、そのjpgパスを返す。"""
    if not videos:
        return None
    step = max(1, len(videos) // sample_videos)
    picked = videos[::step][:sample_videos]
    tmpdir = tempfile.mkdtemp(prefix="autothumb_")
    best, best_score = None, -1.0
    n = 0
    for v in picked:
        d = duration(v)
        if d <= 0:
            continue
        for k in range(per_video):
            ts = max(0.2, d * (k + 1) / (per_video + 1))
            f = os.path.join(tmpdir, f"f{n:04d}.jpg"); n += 1
            r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{ts:.2f}", "-i", v,
                                "-frames:v", "1", "-q:v", "2", f], capture_output=True, timeout=90)
            if r.returncode != 0 or not os.path.exists(f) or os.path.getsize(f) == 0:
                continue
            im = cv2.imread(f)
            if im is None or has_bare_face(im):
                continue
            sc = quality(im)
            if sc > best_score:
                best_score, best = sc, f
    return (best, tmpdir) if best else (None, tmpdir)


def write_square(src, dest):
    from PIL import Image
    im = Image.open(src).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    im.resize((800, 800), Image.LANCZOS).save(dest, quality=88)


# ---------- git ----------

def git(*args, check=True):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True, check=check)


def main():
    if not NOTION_TOKEN:
        print("ERROR: NOTION_TOKEN が無い", file=sys.stderr); return 1
    if not os.path.isdir(SSD_ROOT):
        print("SKIP: SSDが未接続"); return 0

    targets = fetch_targets()
    if not targets:
        print("画像が無い商品はなし"); return 0

    dirs = [d for d in os.listdir(SSD_ROOT)
            if os.path.isdir(os.path.join(SSD_ROOT, d)) and not d.startswith(".")
            and d not in ("⭕️完成動画", "⭐️テンプレフォルダ")]

    done, skipped = [], []
    for item in targets:
        folder = find_folder(item, dirs)
        if not folder:
            skipped.append((item["name"], "SSDフォルダなし")); continue
        vids = collect_videos(folder)
        if not vids:
            skipped.append((item["name"], "自前素材なし")); continue
        frame, tmpdir = best_frame(vids)
        try:
            if not frame:
                skipped.append((item["name"], "素顔なしのコマが見つからず")); continue
            fn = safe_filename(item["name"]) + ".jpg"
            write_square(frame, os.path.join(IMAGES, fn))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        set_thumb(item["ids"], fn)
        done.append((item["name"], fn))
        print(f"OK {item['name']} -> {fn}")

    if done:
        git("add", "images")
        if git("diff", "--staged", "--quiet", check=False).returncode != 0:
            git("commit", "-m", f"Auto-add catalog thumbnails ({len(done)} items)")
            git("fetch", "origin")
            r = git("rebase", "origin/main", check=False)
            if r.returncode != 0:
                git("rebase", "--abort", check=False)
                print("ERROR: rebaseに失敗。手動で確認が必要", file=sys.stderr)
                return 1
            git("push", "origin", "main")

    print(f"追加 {len(done)}件 / 見送り {len(skipped)}件")
    for n, why in skipped:
        print(f"  見送り: {n} — {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
