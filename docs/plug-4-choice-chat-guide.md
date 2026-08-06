# PLuG チャット「4択プロンプト → エージェントへ送信」実装ガイド

**対象読者**: DevRev PLuG を自社サイトに埋め込み、**よくある質問を4つ（または複数）ボタン表示 → クリックでチャットを開き、選択内容をエージェントに渡したい** 担当者  
**前提**: HTML / JavaScript の基本、環境変数の設定ができること  
**リポジトリ**: [devrev-samplesite](https://github.com/konchangakita/devrev-samplesite)（本ガイドの実装例）

---

## 1. この仕組みで実現すること

| ユーザー操作 | 結果 |
|-------------|------|
| ページ上の **4択ボタン**（例:「予約の変更」「アレルギー対応」）をクリック | PLuG チャットが開く |
| **自動送信モード**（AAT 設定時） | 選択した文言が **初回メッセージとして即送信** され、エージェントが応答を開始 |
| **プリフィルモード**（AAT 未設定時） | チャット入力欄に文言が **あらかじめ入った状態** で開く（ユーザーが Send を押す） |

ゴールは **「Send us a message」をユーザーに押させず、サイト側の導線から会話を始められる** ことです。

---

## 2. 全体像（3レイヤ）

```
┌─────────────────────────────────────────────────────────────┐
│ ① 画面（HTML）                                               │
│   4つの <button class="plug-prompt" data-prompt="...">       │
└───────────────────────────┬─────────────────────────────────┘
                            │ クリック
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ ② ブラウザ（plug.js / plugSDK）                              │
│   openPlugConversation(text)                                 │
│     ├─ 自動送信 ON → fetch POST /api/plug/create-conversation│
│     └─ 自動送信 OFF → toggleWidget(..., startConversationContent) │
└───────────────────────────┬─────────────────────────────────┘
                            │ AAT + session token
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ ③ 自社サーバ → DevRev API                                    │
│   internal/conversations.create（初回メッセージ付き会話作成）   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    DevRev エージェント（Computer / 人間）
```

**ポイント**: ブラウザから DevRev API を直接叩くのではなく、**自社バックエンド経由** にすると Application Access Token（AAT）を安全に使え、RevUser の session と整合した会話を作れます。

---

## 3. 2つの動作モード

| モード | 条件 | ユーザー体験 | 実装の中心 |
|--------|------|-------------|-----------|
| **B. プリフィル** | `DEVREV_PLUG_APP_ID` のみ | チャット開く + 入力欄に文言 | `plugSDK.toggleWidget(true, "create_conversation", { startConversationContent })` |
| **A. 自動送信** | 上記 + **`DEVREV_APPLICATION_ACCESS_TOKEN`（AAT）** | クリック → 送信済み会話が開く | サーバ `POST /api/plug/create-conversation` → `conversations.create` |

サンプルでは **`plug_auto_send`** が AAT の有無で自動切り替えします。

```python
# helpsite/main.py（概念）
"plug_auto_send": bool(resolved_application_access_token())
```

---

## 4. ファイル構成（サンプルサイト）

| パス | 役割 |
|------|------|
| `sites/*/templates/_plug_prompt_choices.html` | 4択 UI（ボタングリッド） |
| `sites/*/templates/index.html` 等 | `plug_prompts` 配列の定義 + include |
| `sites/*/templates/base.html` | PLuG SDK 読み込み、`openPlugConversation` 等の JS |
| `shared/devrev/plug_conversation_create.py` | DevRev `conversations.create` 呼び出し |
| `sites/*/helpsite/main.py`（または `employee_site/main.py`） | `/api/plug/create-conversation` API |

---

## 5. ステップバイステップ — 自サイトに載せる

### Step 0: DevRev 側の準備

1. DevRev で **PLuG アプリ** を作成し、**App ID** を取得 → `DEVREV_PLUG_APP_ID`
2. **自動送信** を使う場合は **Application Access Token（AAT）** を発行 → `DEVREV_APPLICATION_ACCESS_TOKEN`
3. エージェント（Computer 等）が PLuG チャットに応答するよう設定

`.env.example` を参照:

```bash
DEVREV_PLUG_APP_ID=your-plug-app-id
DEVREV_APPLICATION_ACCESS_TOKEN=your-aat-token   # 自動送信に必要
```

---

### Step 1: PLuG SDK をページに読み込む

```html
<script src="https://plug-platform.devrev.ai/static/plug.js"></script>
<script>
  window.plugSDK.init({
    app_id: "YOUR_PLUG_APP_ID",
    locale: "ja-JP",
    enable_default_launcher: true,
    widget_alignment: "right",
    spacing: { bottom: "20px", side: "20px" }
  });
</script>
```

**自動送信時は追加**: ウィジェットとサーバで **同じ RevUser session** を使うため `fetchSessionToken` を設定します（サンプル `base.html` 参照）。

```javascript
initOpts.fetchSessionToken = function () {
  return fetch("/api/plug/session-token", { credentials: "include" })
    .then(function (r) { return r.json(); })
    .then(function (d) { return d.access_token; });
};
```

`ON_PLUG_WIDGET_READY` まで 4択クリックをキューに入れ、ready 後に処理する実装もサンプルに含まれます。

---

### Step 2: 4択 UI を置く

**テンプレート例**（`_plug_prompt_choices.html`）:

```html
<section class="plug-prompt-panel">
  <h2>チャットで相談</h2>
  <p>よくあるご質問を選ぶと、選択内容がエージェントに送られます。</p>
  <div class="plug-prompt-grid">
    <button type="button" class="plug-prompt"
      data-prompt="予約の変更・キャンセルについて教えてください。">
      <span class="plug-prompt__label">予約の変更・キャンセル</span>
      <span class="plug-prompt__desc">予約番号がわからない場合も</span>
    </button>
    <!-- 残り3つ同様 -->
  </div>
</section>
```

**データの定義例**（Jinja2 / 任意のテンプレート）:

```python
plug_prompts = [
  {
    "label": "予約の変更・キャンセル",           # ボタンに見せる短い文言
    "description": "予約番号がわからない場合も",  # 補足（任意）
    "message": "予約の変更・キャンセルについて教えてください。..."  # エージェントに渡す本文
  },
  # ... 計4件
]
```

| フィールド | 用途 |
|-----------|------|
| `label` | ボタン見出し（短く） |
| `description` | サブテキスト（任意） |
| `message` | **実際に送る / プリフィルするテキスト**（ここがエージェントの入力） |

---

### Step 3: クリック → チャットを開く（JavaScript）

```javascript
document.addEventListener("click", function (e) {
  var btn = e.target.closest(".plug-prompt");
  if (!btn) return;
  openPlugConversation(btn.getAttribute("data-prompt") || "");
});

function openPlugConversation(text) {
  text = String(text || "").trim();

  // 自動送信モード（AAT あり）
  if (plugAutoSend && text) {
    fetch("/api/plug/create-conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ csrf_token: window.__CSRF__, message: text })
    })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        var id = j.conversation_don || j.conversation_id;
        if (id) {
          window.plugSDK.toggleWidget(true, "conversations_view", { id: id });
          applyPlugPromptSessionProperties(text);
          return;
        }
        openPlugConversationPrefill(text);  // 失敗時フォールバック
      })
      .catch(function () { openPlugConversationPrefill(text); });
    return;
  }

  // プリフィルモード
  openPlugConversationPrefill(text);
}

function openPlugConversationPrefill(text) {
  window.plugSDK.toggleWidget(true, "create_conversation", {
    startConversationContent: text
  });
  applyPlugPromptSessionProperties(text);
}
```

**セッション属性（任意・推奨）**: どのボタンから来たかをエージェント側で参照できるよう付与します。

```javascript
window.plugSDK.addSessionProperties({
  plug_prompt_message: text.slice(0, 500),
  plug_prompt_source: "plug-prompt-choices"
});
```

---

### Step 4: サーバ API — 会話を作成して送信

**エンドポイント**: `POST /api/plug/create-conversation`

**リクエスト**:

```json
{
  "csrf_token": "...",
  "message": "予約の変更・キャンセルについて教えてください。"
}
```

**レスポンス（成功）**:

```json
{
  "ok": true,
  "conversation_id": "CONV-123",
  "conversation_don": "don:core:dvrv-us-1:devo/...:conversation/..."
}
```

**サーバ実装の芯**（`shared/devrev/plug_conversation_create.py`）:

- URL: `https://api.devrev.ai/internal/conversations.create`
- Authorization: **RevUser の PLuG session JWT**（`Bearer ...`）
- Body: `messages[0].body` にユーザーが選んだ `message`
- Header: `X-Devrev-Client-Platform: plug-widget`（ウィジェットと同型）

```python
def create_plug_support_conversation(session_token: str, message: str, *, url_context: str):
    payload = {
        "type": "support",
        "source_channel": "chat",
        "messages": [{"body": message.strip(), "artifacts": [], "client_ref": "..."}],
        "metadata": {"url_context": url_context},
    }
    # POST with Authorization: Bearer <session_token>
```

**session token の取得**: ログインユーザーまたは匿名ゲスト用に、サーバが DevRev API で RevUser session を発行し、Cookie セッションに保持。`/api/plug/session-token` で PLuG `fetchSessionToken` に返します。

---

## 6. 環境変数チェックリスト

| 変数 | 必須 | 用途 |
|------|------|------|
| `DEVREV_PLUG_APP_ID` | ✅（PLuG 自体） | `plugSDK.init({ app_id })` |
| `DEVREV_APPLICATION_ACCESS_TOKEN` | 自動送信時 ✅ | session 発行 + `plug_auto_send=true` |
| `DEVREV_PAT` | 任意 | 会話カスタムフィールド同期（IP 等）— 4択送信とは別機能 |
| `SECRET_KEY` | ✅（サンプル） | セッション Cookie |

---

## 7. 動作確認手順

1. `.env` に `DEVREV_PLUG_APP_ID` を設定 → サイト起動
2. 4択が表示されるページを開く（例: `/restaurant/` トップ）
3. **プリフィルのみ**（AAT なし）  
   - ボタンクリック → チャットが開き、入力欄に `message` が入っている
4. **自動送信**（AAT あり）  
   - ボタンクリック → 会話画面が開き、**ユーザー送信なしで** 初回メッセージがスレッドに存在
5. DevRev 側の会話一覧で、メッセージ内容と RevUser が期待どおりか確認

**デバッグ**: URL に `?plug_debug=1` を付けるとコンソールに PLuG イベント・API 結果が出ます（レストランサイト `base.html`）。

---

## 8. よくあるつまずき

| 症状 | 原因の例 | 対処 |
|------|---------|------|
| 4択が表示されない | `plug_enabled` / `plug_app_id` 未設定 | `.env` の App ID、テンプレートの `{% if plug_enabled %}` |
| クリックしても何も起きない | SDK 未 ready | `ON_PLUG_WIDGET_READY` 後に `flushPendingPlugConversation` |
| 自動送信が 503 | AAT 未設定 or session 未取得 | `DEVREV_APPLICATION_ACCESS_TOKEN`、`/api/plug/session-token` |
| プリフィルは動くが送信されない | 想定どおり（AAT なし） | AAT を設定するか、プリフィル運用を許容 |
| 会話はできるがエージェントが応答しない | DevRev 側ルーティング | Computer / キュー設定を DevRev 管理画面で確認 |
| CSRF エラー | トークン不一致 | ページの `window.__CSRF__` と POST body を一致 |

---

## 9. カスタマイズのヒント

### 4択の文言を変える

`index.html`（または該当ページ）の `plug_prompts` 配列だけ編集すれば OK。コード変更は不要です。

### 5択・3択にする

`plug_prompts` の要素数を増減。CSS グリッド（`.plug-prompt-grid`）はサンプルでレスポンシブ対応済み。

### 特定ボタンだけプリフィルにしたい

```html
<button class="plug-prompt" data-prompt="..." data-auto-send="false">
```

`openPlugConversation` の `options.autoSend` で制御（サンプル `base.html`）。

### 他ページから同じ関数を呼ぶ

```javascript
window.openPlugConversation("コースメニューの料金を教えてください。");
```

---

## 10. AI と相談しながら作るときのプロンプト例

以下をそのまま ChatGPT / Claude / Cursor に貼り、自社スタックに合わせて改変できます。

### プロンプト A — 要件整理

```
自社サイトに DevRev PLuG チャットがあります。
よくある質問4つをボタン表示し、クリックで
(1) チャットを開く
(2) 選択文言を初回メッセージとしてエージェントに渡す
実装したいです。

フロントは [React / 素の HTML / Next.js 等]、
バックエンドは [FastAPI / Node / なし 等] です。

devrev-samplesite の plug-4-choice-chat-guide.md の
「自動送信モード」と「プリフィルモード」の違いを踏まえ、
必要な環境変数と API 一覧を整理してください。
```

### プロンプト B — フロント実装

```
PLuG plug.js は読み込み済みです。
4つの button.plug-prompt に data-prompt を付けています。

plug_auto_send が true のとき:
  POST /api/plug/create-conversation { message }
  → 返却 conversation_id で toggleWidget("conversations_view")

false のとき:
  toggleWidget(true, "create_conversation", { startConversationContent: message })

ON_PLUG_WIDGET_READY 前のクリックはキューに入れて後から実行する
ヘルパーを [言語] で書いてください。
```

### プロンプト C — バックエンド実装

```
DevRev internal/conversations.create をサーバから呼びます。
Authorization は RevUser の PLuG session JWT（Bearer）です。
Body は devrev-samplesite の plug_conversation_create.py と同型にしてください。

エンドポイント POST /api/plug/create-conversation
- CSRF 検証
- session token をサーバセッションから解決
- message 1〜2000 文字
- 成功時 { ok, conversation_id, conversation_don }

[FastAPI / Express] で実装例を出してください。
```

---

## 11. 関連ドキュメント（サンプルリポジトリ内）

| ドキュメント | 内容 |
|-------------|------|
| [docs/DESIGN.md](./DESIGN.md) | サイト全体設計 |
| [sites/restaurant/docs/plug-ip-sync-flow.md](../sites/restaurant/docs/plug-ip-sync-flow.md) | session 属性・IP 同期（4択とは別だが PLuG 連携） |
| [docs/future-multi-plug.md](./future-multi-plug.md) | サイト別 App ID の将来方針 |

---

## 12. まとめ

| やりたいこと | 最小構成 |
|-------------|---------|
| 4択表示 + 入力欄プリフィル | App ID + `_plug_prompt_choices.html` + `toggleWidget(... startConversationContent)` |
| **クリック即送信（本番想定）** | 上記 + **AAT** + `/api/plug/create-conversation` + `conversations.create` + `fetchSessionToken` |

サンプル実装は **レストラン**（`/restaurant/`）と **社内ヘルプ**（`/employee/`）の両方に同型で入っています。まずレストランの `index.html` と `base.html` を読むと、全体の流れを最短で追えます。

---

**ドキュメント版**: 2026-07-22  
**実装参照**: `devrev-samplesite` @ main（`sites/restaurant`, `shared/devrev/plug_conversation_create.py`）
