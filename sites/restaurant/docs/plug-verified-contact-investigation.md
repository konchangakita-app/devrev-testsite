# PLuG verified Contact 調査メモ（kon-jp / 2026-08-04）

## 調査経緯（時系列）

### 1. 問題の発生（kon201 / kon202）

- 会員登録・ログイン後、DevRev 上の Contact が **Unverified** のまま
- 実装は公式の verified フロー（AAT → `auth-tokens.create` → `plugSDK.init({ session_token })`）に沿っているはず
- `user_ref` は `mbr:{会員ID}` 形式

### 2. Cookie 4KB 問題の発見と修正（コミット `065ae4e`）

- **原因:** 匿名 PLuG トークン + 会員トークンで Cookie が 4KB 超 → ブラウザがセッション破棄
- **修正:** ログイン時に `devrev_anon_session_token` / `plug_anon_user_ref` をセッションから除去
- **結果:** ログイン・session token 埋め込みは正常化したが、verified 化には至らず

### 3. 新規ユーザーでの再検証（kon203 / kon204）

- Cookie 修正後に新規登録 → 依然 `is_verified: false`
- **判明:** サーバー側の `auth-tokens.create` だけでは verified にならない。ブラウザ PLuG init も必要

### 4. PLuG 側の問題修正

- 会員ログイン中の **匿名 PLuG 再 init フォールバック**を無効化（verified 上書き防止）
- **`fetchSessionToken` と埋め込み `session_token` の競合**を回避
- 調査用 env 追加（`DEVREV_PLUG_USER_REF`, `DEVREV_PLUG_REQUESTED_TOKEN_TYPE`, `DEVREV_PLUG_DEFER_SESSION_ON_AUTH`）

### 5. 追加試行（kon205〜209）— すべて unverified

| 試行内容 | ユーザー | 結果 |
|---------|---------|------|
| `user_ref=email` | kon205 | false |
| `requested_token_type=session_rev_public` | kon206 | false |
| ブラウザ PLuG init 確認（`ON_PLUG_WIDGET_READY`） | kon206/208 | false |
| 登録時 token 発行遅延（defer） | kon209 | false |

- いずれも AAT + session token + PLuG init は動作するが **`is_verified: false`**
- verified 例 +113 は `created_by: dev_user`（管理画面手動）、テストユーザーは `created_by: sys_user`

### 6. DevRev 公式調査・問い合わせ準備

- 公式制約確認: unverified → verified の変換・マージ不可、同一 `user_ref` 再利用不可
- 試行一覧を [plug-verified-contact-support-inquiry.md](./plug-verified-contact-support-inquiry.md) に整理

### 7. 根本原因の判明 — **Public AAT**

- DevRev 側確認: **Public AAT（`tokentype: aat:public`）では verified Contact が作成できない**
- 非 Public AAT（`tokentype: aat`）が必要
- 旧 AAT: svcacc/68, `urn:...:token-type:aat:public`

### 8. 非 Public AAT への切替と成功（kon212）

- ルート `.env` を新 AAT（svcacc/117, `urn:...:token-type:aat`）に更新
- **落とし穴:** `sites/restaurant/.env` がルート `.env` を**上書き**していたため、最初の kon210/211 テストでは旧 Public AAT が使われていた
- 両方更新 + サーバー再起動後、**kon212**（ブラウザ登録 + PLuG init）→ **`is_verified: true` ✅**

### 9. 結論

| 項目 | 内容 |
|------|------|
| **根本原因** | Public AAT 使用 |
| **解決策** | 非 Public AAT + 公式 verified フロー（実装済み） |
| **既存 unverified** | 昇格不可。削除して新 `user_ref` で作り直し |
| **AAT 設定注意** | ルート `.env` と `sites/restaurant/.env` の**両方**を更新すること |

---

## 背景

会員ログイン + AAT による `auth-tokens.create` → `plugSDK.init({ session_token })` フローで、DevRev 上の Contact が `is_verified: true` になるはずだが、テストユーザー（kon201 以降）が Unverified のままになる問題を調査した。

公式: [Identify your users with Plug](https://developer.devrev.ai/sdks/web/user-identity)

## 環境

| 項目 | 値 |
|------|-----|
| Org | kon-jp（`dvrv-jp-1`） |
| ローカル | `uvicorn` 直起動（port 5020）。Docker Compose も利用可（README 参照） |
| AAT（旧） | Public（`aat:public`, svcacc/68）— verified 不可 |
| AAT（新） | 非 Public（`aat`, svcacc/117）— verified 可 |
| DB | Neon PostgreSQL |

## テストユーザー（パスワードはすべて `demo1234`）

| ユーザー | メール | user_ref 方式 | token type | is_verified | 備考 |
|---------|--------|---------------|------------|-------------|------|
| kon201 | +201 | `mbr:3` | session | false | Cookie 4KB 問題修正前 |
| kon202 | +202 | `mbr:4` | session | false | 同上 |
| kon203 | +203 | `mbr:5` | session | false | Cookie 修正後 |
| kon204 | +204 | `mbr:6` | session | false | 同上 |
| kon205 | +205 | email | session | false | user_ref=email 初回 |
| kon206 | +206 | email | session_rev_public | false | ブラウザ PLuG init 済 |
| kon207 | +207 | email | — | false | API テストで誤作成 |
| kon208 | +208 | email | session | false | fetchSessionToken 競合修正後 |
| kon209 | +209 | email | session | false | 登録時 token 発行遅延（defer） |
| kon210 | +210 | email | session | false | 新 AAT 設定後も site .env 上書きで Public 残存 |
| kon211 | +211 | email | session | false | 同上 |
| **kon212** | **+212** | **email** | **session** | **true ✅** | **非 Public AAT 適用後・初回成功** |

## 実装との対応（公式 verified フロー）

| 要件 | 実装 |
|------|------|
| バックエンドで AAT を保持 | ✅ `.env` |
| `auth-tokens.create` + `rev_info` | ✅ `devrev_service.py` |
| `plugSDK.init({ session_token })` | ✅ `base.html` |
| フロントに `identity` を直接渡さない | ✅ 未使用 |

## 実施した修正・試行

1. **Cookie 4KB 超過**（コミット `065ae4e`）  
   ログイン時に匿名 PLuG トークンをセッションから除去。会員セッションがブラウザに保存されなくなる問題を解消。

2. **会員ログイン中の匿名 PLuG フォールバック無効化**（`base.html`）  
   `session_token` 付き init 後、8 秒以内に ready にならない場合でも、会員ログイン中は匿名再 init しない。

3. **調査用 env**（`.env` のみ、コミットしない）  
   - `DEVREV_PLUG_USER_REF=email` … `user_ref` をメールに  
   - `DEVREV_PLUG_REQUESTED_TOKEN_TYPE=session` \| `session_rev_public`  
   - `DEVREV_PLUG_DEFER_SESSION_ON_AUTH=true` … 登録/ログイン時の `auth-tokens.create` をスキップ

4. **fetchSessionToken 競合回避**（`base.html`）  
   会員 + 埋め込み `sessionToken` があるときは `fetchSessionToken` を設定しない。

5. **会員ページ表示**（`member.html`）  
   DevRev `user_ref` モードと RevUser DON を表示。

## 観測結果

### ブラウザ側

- `plugSDK.init({ session_token })` は実行される（`ON_PLUG_WIDGET_READY` まで到達）
- `POST /internal/rev-users.self.update` が 200（PLuG が RevUser を認識）
- それでも `rev-users.list` の `is_verified` は **false** のまま

### verified 例との差分（+113）

| 項目 | +113（verified） | kon208/209（unverified） |
|------|------------------|--------------------------|
| `created_by` | `dev_user`（satoru-kondou） | `sys_user`（devrev-bot） |
| 作成経路 | DevRev 管理画面で手動作成の可能性 | `auth-tokens.create`（AAT）経由 |
| created / modified | 同一タイムスタンプ | PLuG init 後に modified が更新 |

**+113 は PLuG セッショントークンフローではなく、DevRev UI 上で手動作成された Contact の可能性が高い。**

### auth-tokens.create の挙動

- サーバー側の `auth-tokens.create` 呼び出し時点で RevUser が **sys_user により作成**される
- その時点で `is_verified: false`
- その後ブラウザで PLuG init しても **verified に昇格しない**

### defer 試行（kon209）

- `DEVREV_PLUG_DEFER_SESSION_ON_AUTH=true` で登録直後は DevRev 上 Contact **0 件**を確認
- 会員ページ表示時（`page_context` → `resolve_plug_session_token`）に初めて `auth-tokens.create` → 依然 **unverified**

## DevRev 制約（公式）

- Unverified は verified に変換・マージ不可
- Unverified が使った `external_ref` / `user_ref` は再利用不可  
  → 同一 ref で verified を試すには DevRev 上で Contact 削除が必要

## 結論（現時点）

kon-jp org では、**Public AAT（`aat:public`）では verified Contact が作成できない**。非 Public AAT（`urn:...:token-type:aat`）が必要（2026-08-04 DevRev 側確認）。

Public AAT 使用時は、AAT + `auth-tokens.create` + `plugSDK.init(session_token)` を正しく実装しても **`is_verified: true` にならない**。

## 非 Public AAT 切替後の検証（kon212）

- `.env` および **`sites/restaurant/.env`**（こちらがルートを上書きしていた）の AAT を非 Public（`tokentype: aat`, svcacc/117）に差し替え
- サーバー再起動後、kon212（ブラウザ登録 + PLuG init）→ **`is_verified: true` ✅**
- kon210 / kon211 は切替前の Public AAT で作成されたため unverified のまま（削除して作り直しが必要）

## 次のアクション案

1. ~~DevRev Settings → Support → PLuG Tokens で **AAT を再発行**~~ → **非 Public AAT を使用**（済）
2. 旧 Public AAT で作成した unverified Contact（kon201〜211 等）を snap-in 等で削除
3. 非 Public AAT で **新 `user_ref`** を verified フローで作り直す（kon212 で成功確認済み）
4. **`sites/restaurant/.env` がルート `.env` より優先される**ため、AAT 変更時は両方を更新すること

## 関連ファイル

- `sites/restaurant/helpsite/devrev_service.py` — token 発行
- `sites/restaurant/templates/base.html` — PLuG init
- `sites/restaurant/helpsite/main.py` — セッション解決・defer
- `sites/restaurant/helpsite/config.py` — 調査用 env キー

## ローカル確認コマンド

```bash
# DevRev 上の is_verified 確認（kon-jp PAT）
eval "$(python3 .../devrev_pat_cli.py resolve --profile kon-jp --export-shell --show-token)"
curl -s -X POST "$DEVREV_API_BASE/rev-users.list" \
  -H "Authorization: Bearer $DEVREV_PAT" \
  -H "Content-Type: application/json" \
  -d '{"email":["konchangakita+212@gmail.com"]}'
```

## 関連ドキュメント

- [plug-verified-contact-support-inquiry.md](./plug-verified-contact-support-inquiry.md) — DevRev 公式問い合わせ用（試行一覧・解決記載済み）
