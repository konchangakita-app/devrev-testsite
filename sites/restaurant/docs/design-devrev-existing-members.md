# 既存会員 × DevRev（PLuG）連携の設計メモ

既存顧客 DB に DON 列を追加せず、**会員 ID を正**として Rev ユーザーを解決・作成する前提の整理です。プラン「既存会員と DevRev SDK 連携の設計検討」の To-do を反映しています。

---

## 1. Webhook / イベント利用時の相関（clarify-webhooks）

### DevRev の Webhook の性質

- Webhook はイベント種別ごとにペイロードが届き、`type` に続くフィールドにオブジェクトが入る（[Webhooks ガイド](https://developer.devrev.ai/public/guides/webhooks)）。
- **オブジェクトのスキーマは OpenAPI と同じ**とされており、`rev_user_created` 等を購読する場合は **Rev User オブジェクト**が含まれる。
- 署名は `X-DevRev-Signature`（HMAC-SHA256）で検証する。

### 「会員 ID がペイロードに無い」リスク

- Webhook 本文が **Rev ユーザーの DON（`don:...:revu/...`）中心**で届く場合、**自社会員 ID が直接含まれない**と、レガシー DB を変更せず **DON → 会員 ID** の逆引きができない。

### 推奨される対応（いずれか／併用）

| 方針 | 内容 |
|------|------|
| **A. user_ref を会員 ID に固定** | `auth-tokens.create` の `rev_info.user_ref` を常に **`mbr:{会員ID}` のような規則付き文字列**にする。Rev 側の表示・検索で `user_ref` が追える場合、運用・サポートで人間が紐づけ可能。 |
| **B. user_traits に外部キーを載せる** | `user_traits.email` や **カスタム属性**（組織で定義したフィールド）に、運用上許容なら **会員 ID または外部参照**を入れる。Webhook の Rev User 拡張に含まれる場合、受信側でパース可能かは **スキーマと実際のペイロードで要確認**。 |
| **C. Rev Users API で補完** | Webhook で DON だけ受け取ったら、サーバから **`rev-users.get` 等**で Rev ユーザーを取得し、`external_ref` や traits を読む（API が返すフィールドに依存）。 |
| **D. レガシー DB を触らない別ストア** | Webhook 受信後だけ **Redis / 連携用 DB（別スキーマ）** に `DON → 会員ID` を短 TTL または永続で保持（本番会員マスタは変更しない）。 |

### 結論

- **Webhook を使うか**はプロダクト次第。**使う場合**は上記のいずれかで **DON と会員 ID の橋**を用意する。
- **PLuG のみ**（同期イベントが不要）なら、**毎回 `auth-tokens.create`（user_ref = 会員 ID）** だけでも運用可能で、Webhook は必須ではない。

---

## 2. 会員 ID を `user_ref` にする規則（define-user-ref）

DevRev の `user_ref` は **アプリ内でユーザーを一意に識別する文字列**（[PLuG User identity](https://developer.devrev.ai/public/sdks/web/user-identity)）。既存会員 ID をそのまま使う場合の推奨ルール例:

| 項目 | 推奨 |
|------|------|
| **形式** | 固定プレフィックス + 正規化済み ID。例: `mbr:123456789`（数値 ID のゼロ埋め規則を DB 側で一本化してから連結）。 |
| **文字セット** | ASCII の英数字と区切りに限定（URL・ログに安全）。 |
| **大小文字** | 正規化（例: 常に小文字のみ）して一意性を担保。 |
| **変更** | 会員 ID の **マージ・再発番**があると、別 `user_ref` になり **別 Rev ユーザー**になり得る。変更時は DevRev 側の運用（マージ API の有無）と合わせて方針を決める。 |
| **重複** | 同一 DevOrg で **同一 `user_ref` は一意**前提。テスト環境と本番で同じ AAT を使う場合の衝突に注意。 |

`sample-helpsite` の [`devrev_service.py`](../helpsite/devrev_service.py) は現状 `user_ref = user.email` だが、本番では **`user_ref = f"mbr:{membership_id}"` のように差し替える**想定になる。

---

## 3. DON を永続保存しないときの揮発キャッシュ（optional-cache）

DON を顧客 DB に持たない場合でも、次の用途では **短時間だけ** DON またはセッション JWT を保持するとよい。

| ユースケース | 案 |
|--------------|-----|
| **同一セッション内で PLuG を再初期化** | サーバセッションに `devrev_session_token` を保存（helpsite と同様）。DB 変更なし。 |
| **バックエンドが Rev API を DON で呼ぶ** | ログイン直後に一度 `auth-tokens.create` し、**Redis** に `member:{id} → DON` または JWT を **TTL 5〜15 分**で保存。 |
| **監査** | 永続が必要なら **別系統の監査ログ**（会員 ID + タイムスタンプ + イベント種別）のみ。DON 全文はマスク。 |

**不要なら**毎リクエスト `auth-tokens.create`（レート制限・レイテンシに注意）でもよいが、本番では **キャッシュ + 失敗時リトライ**が現実的。

---

## 4. 参考: 本リポジトリのコードとの対応

| 項目 | 実装箇所 |
|------|----------|
| `auth-tokens.create` | [`helpsite/devrev_service.py`](../helpsite/devrev_service.py) |
| JWT `sub` → DB（DON 保存する場合） | 同上（任意。既存会員方針では保存しないことも可） |
| 管理 API（DON クエリ） | [`helpsite/admin_user.py`](../helpsite/admin_user.py)（会員 ID キーにしたい場合は **別 API** を自前で用意するのが自然） |

---

## 5. チェックリスト（導入前）

- [ ] Webhook を使うか。使うなら **DON → 会員 ID** の橋（B〜D のいずれか）。
- [ ] `user_ref` の文字列規則をドキュメント化し、会員 ID 変更時の運用を決めたか。
- [ ] `account_ref` / `workspace_ref` を送るか（B2C なら空で送らない選択可）。
- [ ] AAT の保管・ローテーションと、`auth-tokens.create` のレート・失敗時の UX。
