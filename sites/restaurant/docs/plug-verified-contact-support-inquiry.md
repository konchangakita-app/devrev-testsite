# DevRev 公式問い合わせ用：verified Contact が作成できない問題

> 調査日: 2026-08-04  
> Org: kon-jp（`dvrv-jp-1` / `DEV-6M2YuzjOnn`）  
> 関連: [plug-verified-contact-investigation.md](./plug-verified-contact-investigation.md)

---

## 問い合わせ概要

**製品:** PLuG Web SDK + Application Access Token（AAT）

**期待:** 公式ドキュメント [Identify your users with Plug](https://developer.devrev.ai/sdks/web/user-identity) に従い、AAT → `auth-tokens.create` → `plugSDK.init({ session_token })` で Contact が **verified**（`is_verified: true`）になる

**実際:** 上記フローを実装・検証しても、作成された RevUser はすべて **`is_verified: false`（Unverified）のまま**

---

## 実装内容（公式 verified フローとの対応）

| 公式要件 | 当方の実装 |
|---------|-----------|
| AAT をバックエンドのみで保持 | ✅ サーバー `.env` のみ。フロントに AAT は出さない |
| `auth-tokens.create` で session token 取得 | ✅ `POST https://api.devrev.ai/auth-tokens.create` + `rev_info` |
| `plugSDK.init({ app_id, session_token })` | ✅ `session_token` を HTML に埋め込み init |
| フロントに `identity: { user_ref, user_traits }` を直接渡さない | ✅ 未使用 |

`auth-tokens.create` リクエスト例:

```json
{
  "requested_token_type": "urn:devrev:params:oauth:token-type:session",
  "rev_info": {
    "user_ref": "konchangakita+209@gmail.com",
    "user_traits": {
      "email": "konchangakita+209@gmail.com",
      "display_name": "kon209",
      "phone_numbers": []
    }
  }
}
```

AAT JWT の `scope`: `urn:devrev:params:oauth:token-type:session:rev`  
AAT JWT の `tokentype`（旧・問題あり）: `urn:devrev:params:oauth:token-type:aat:public`  
AAT JWT の `tokentype`（新・verified 用）: `urn:devrev:params:oauth:token-type:aat`

> **根本原因（2026-08-04 判明）:** Public AAT（`aat:public`）では verified Contact が作成できない。非 Public AAT（`aat`）が必要。

---

## 試してうまくいかなかったこと（時系列）

### 1. 基本的な verified フロー（`user_ref = mbr:{id}`）

- **手順:** 会員登録 → ログイン → 会員ページで PLuG 読み込み
- **user_ref:** `mbr:3`, `mbr:4`, `mbr:5`, `mbr:6`（kon201〜204）
- **結果:** すべて `is_verified: false`
- **補足:** 当初 Cookie 4KB 超過で session token がブラウザに届かない問題があったが修正後（kon203/204）も同様

### 2. Cookie / セッション問題の修正後も verified にならない

- **修正:** ログイン時に匿名 PLuG トークン（`devrev_anon_session_token` 等）をセッションから削除
- **確認:** ログイン後 Cookie サイズは 4KB 以内、会員ページ HTML に `sessionToken` が埋め込まれる
- **結果:** kon203 / kon204 も `is_verified: false` のまま

### 3. `user_ref` をメールアドレスに変更

- **理由:** org 内の verified 例（`konchangakita+113@gmail.com`）は `external_ref` = メールアドレスだったため
- **設定:** `user_ref` = `konchangakita+205@gmail.com` 等
- **結果:** kon205〜209 すべて `is_verified: false`
- **`external_ref`:** メールは正しく設定されるが verified にならない

### 4. `requested_token_type` の変更

| 試行 | `requested_token_type` | 結果 |
|------|------------------------|------|
| kon205〜208, kon209 | `urn:...:token-type:session` | false |
| kon206 | `urn:...:token-type:session:rev:public` | false |

いずれも session token は HTTP 201 で取得でき、PLuG init も動作するが `is_verified` は false。

### 5. ブラウザで PLuG を確実に init（curl 登録のみ → ブラウザでログイン）

- **手順:** ブラウザでログイン → `/restaurant/member` → PLuG ウィジェット表示
- **確認:**
  - `ON_PLUG_WIDGET_READY` イベント発火
  - `POST https://api.devrev.ai/internal/rev-users.self.update` が 200
  - PLuG ウィジェットを `toggleWidget(true)` で開いた
- **結果:** kon206 / kon208 / kon209 も `is_verified: false` のまま

### 6. 会員ログイン中の匿名 PLuG 再 init を防止

- **問題の仮説:** `session_token` init 失敗時に匿名モードで再 init し、unverified で上書きされる
- **対応:** 会員ログイン中は匿名フォールバックをスキップ
- **結果:** 改善せず。kon208 等も false

### 7. `fetchSessionToken` と埋め込み `session_token` の競合回避

- **問題の仮説:** `plugAutoSend=true` 時、`init` に `session_token` と `fetchSessionToken` が両方渡り挙動が不安定
- **対応:** 会員 + 埋め込み token がある場合は `fetchSessionToken` を設定しない
- **結果:** kon208 も false

### 8. 登録/ログイン時の `auth-tokens.create` を遅延（RevUser 作成タイミングの変更）

- **仮説:** サーバー側で先に RevUser が unverified として作られ、後から PLuG init しても verified にならない
- **手順（kon209）:**
  1. 登録直後 → DevRev 上 Contact **0 件**（`auth-tokens.create` 未実行）
  2. 会員ページ初回表示時に初めて token 発行 + PLuG init
- **結果:** RevUser は作成されるが `created_by: sys_user`、`is_verified: false` のまま

### 9. 同一 org 内の verified 例との比較

| 項目 | verified 例（+113） | 当方テスト（kon209 等） |
|------|---------------------|-------------------------|
| `is_verified` | **true** | **false** |
| `external_ref` | `konchangakita+113@gmail.com` | `konchangakita+209@gmail.com` |
| `created_by.type` | **`dev_user`** | **`sys_user`**（devrev-bot） |
| 作成経路（推定） | DevRev UI 手動作成？ | `auth-tokens.create`（AAT） |

---

## 観測された API / ブラウザの挙動

1. **`auth-tokens.create`** … HTTP 201、session token（JWT）取得は成功
2. **RevUser 作成** … `auth-tokens.create` 呼び出し時点で RevUser が作成される（`created_by: sys_user`）
3. **作成時点の `is_verified`** … すでに **false**
4. **PLuG init 後** … `rev-users.self.update` は成功するが **`is_verified` は true にならない**
5. **`rev-users.update`** … `is_verified` を直接更新する手段は見当たらない（公式制約と理解）

---

## うまくいったこと（参考）

- AAT による `auth-tokens.create`（HTTP 201）
- 会員ログイン後の session token 発行・HTML 埋め込み
- `plugSDK.init({ session_token })` とウィジェット表示
- RevUser の DON 取得、`external_ref` / email の設定
- PLuG 経由の会話開始

---

## DevRev に確認したこと（回答済み）

1. ~~`is_verified` が false のままになる原因~~ → **Public AAT が原因**
2. ~~不足している AAT 種別~~ → **非 Public AAT（`aat`）が必要。Public（`aat:public`）は不可**
3. ~~PLuG init 後に true になる前提条件~~ → 非 Public AAT + verified フロー（実装どおり）
4. +113 との差 → 手動作成 vs AAT フロー。AAT フローでも非 Public なら verified 可能（kon212 で確認）

---

## テスト用 RevUser 一覧

| Email | external_ref | is_verified | 備考 |
|-------|--------------|-------------|------|
| konchangakita+201@gmail.com | mbr:3 | false | Public AAT 時代 |
| konchangakita+202@gmail.com | mbr:4 | false | 同上 |
| konchangakita+205@gmail.com | +205 email | false | 同上 |
| konchangakita+206@gmail.com | +206 email | false | 同上 |
| konchangakita+209@gmail.com | +209 email | false | 同上 |
| konchangakita+210@gmail.com | +210 email | false | site .env 上書きで Public 残存 |
| konchangakita+211@gmail.com | +211 email | false | 同上 |
| **konchangakita+212@gmail.com** | **+212 email** | **true ✅** | **非 Public AAT 適用後** |

---

## 解決（2026-08-04）

**原因:** Public AAT（`tokentype: aat:public`）では verified Contact が作成できない。

**対処:** 非 Public AAT（`tokentype: aat`）に差し替え。  
**注意:** `sites/restaurant/.env` がルート `.env` より後から読み込まれ **上書きする**。AAT 変更時は **両方** を更新し、サーバーを再起動すること。
