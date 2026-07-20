# カタログページ構築 引き継ぎメモ（2026-07-21）

## 目的・背景

TikTokショップ用に作った動画を **YouTube Shorts / Instagram リール** へ横展開する。
末尾（CTA）だけ差し替え、「詳細はプロフィールのリンクから」に誘導する。

- **本当の狙い**：楽天で稼ぐことではなく、IG・YTのフォロワーを育てること
  - Instagram → Temuなど大型案件の固定報酬（月10万〜）を狙う
  - YouTube → ガジェット系の商品提供を狙う
- 楽天アフィリエイト収益は副産物

## 規約確認済み（重要）

- **楽天アフィリエイト認定SNS**：YouTube・Instagram・TikTokはすべて認定済み。直接リンク設置OK
- **PR表記**：「広告」等の表記があればステマ規制の要件を満たす。アフィリ先の明示（「楽天アフィリエイト」等）は不要
- **他人の商品画像の流用はNG**（楽天の商品画像をそのまま使うのは不可）→ 自分で撮影・作成した画像を使う

## 構築済みのもの

### リポジトリ
`https://github.com/123cgo67hachi-creator/kenji-items`

### 公開URL
- **カタログページ**：https://123cgo67hachi-creator.github.io/kenji-items/
- **管理ページ**：https://123cgo67hachi-creator.github.io/kenji-items/admin.html

### ファイル構成
```
kenji-items/
├── index.html          # カタログページ（自動生成・直接編集しない）
├── admin.html          # 管理ページ（商品登録・画像アップ用）
├── generate.py         # Notion → index.html を生成
├── update_notion.py    # admin経由の入力をNotionに書き戻す
├── images/             # サムネイル画像置き場
└── .github/workflows/sync.yml   # 同期ワークフロー
```

### Notion側の変更
案件管理表（DB ID: `fd7b3071-f92a-46d6-8cf4-0eab85108bf9`）に列を2つ追加済み：
- `楽天リンク`（URL型）
- `サムネURL`（URL型）

### 同期の仕組み
- `ステータス = 投稿済み` の案件だけをカタログに表示
- 商品名末尾の①②は除去し、重複は1件にまとめる
- 毎朝 05:30 JST に自動同期（cron: `30 20 * * *` UTC）
- 手動同期は admin.html の「送信」or「画像なしで同期だけ実行」

### GitHub Secrets
- `NOTION_TOKEN` 登録済み

## 管理ページの使い方

1. https://123cgo67hachi-creator.github.io/kenji-items/admin.html を開く
2. 初回のみ GitHub Token を入力して保存（localStorage に保存される）
   - トークンは `gh auth token` で取得
3. 商品を選ぶ → 楽天URL貼る → 画像をドロップ → 送信
4. 1〜2分でカタログに反映

## 現在の状態

- カタログページ：31商品が表示中（全商品「準備中」＝楽天リンク未設定）
- 画像：まだ0件
- admin.html：デプロイ済みだが **実運用テストは未実施**

## 未解決・次にやりたいこと

1. **admin.html の実地テスト**（画像アップ→Notion更新→カタログ反映の一気通貫確認）
2. **GitHubトークンの寿命問題**
   - 現在は `gho_` で始まる gh CLI のOAuthトークンを使う想定
   - セッション切れの可能性あり。Fine-grained PAT（contents:write + actions:write）を作って差し替えるのが本筋
3. **iOSショートカット**：一度試みたが認証情報を埋め込めず断念。admin.html をホーム画面に追加する方針に切り替え済み
4. **サムネ画像の作り方**：`tiktok-thumbnail` スキルで作った画像を admin から上げる想定。ワークフロー未整備
5. **楽天アフィリリンクの取得**：31商品分の楽天リンクをどう効率よく集めるか未検討
6. **YouTube用の導線**：概要欄には楽天直リンクを貼る方針（カタログを経由しない）で合意済み。実装作業は未着手

## 決まっていること（再確認不要）

- ページタイトルは「けんじのオススメアイテム」
- PR表記は「広告・PR」のみ
- デザインの方向性はこのままでOK
- 独自ドメインは当面不要（フォロワーが育ってから検討）
- Notionは非公開のまま。公開するのは生成された静的HTMLのみ
