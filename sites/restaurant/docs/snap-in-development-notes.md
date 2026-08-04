# Snap-in 開発メモ（user_ip / 会話カスタムフィールド）

sample-helpsite で PLuG＋`conversations.update` を通した検証から得た前提を、**Snap-in を別経路で実装する際**に参照できるようメモしています。詳細なブラウザ側の流れは [conversation-user-ip-flow.md](conversation-user-ip-flow.md) を参照してください。

---

## 1. 用語と API（ここを間違えると 400 や空のまま）

| 認識 | 実装での名前 |
|------|----------------|
| 人間・説明・PLuG セッション属性 | **`user_ip`**（`addSessionProperties` のキー例） |
| Conversation のカスタムフィールドを API で書くとき | 多くのテナントで **`tnt__user_ip`** のような **`tnt__` 接頭辞付き API 名**（`conversations.update` の `custom_fields` のキー） |

- 環境変数 **`DEVREV_CONVERSATION_CUSTOM_FIELD_USER_IP`** は **update の JSON に載せるキー**（このリポジトリの既定は `tnt__user_ip`）。
- **`custom_schema_spec`**（`tenant_fragment` / `validate_required_fields` 等）がテナントによって必須・推奨が変わる。本リポジトリの `helpsite/plug_conversation_sync.py` は複数バリアントを試す実装。

---

## 2. このサンプルが既にやっていること（Snap-in と比較する基準）

- **会話 ID** は PLuG の `onEvent`（例: `ON_CONVERSATION_START`）で **`conversation_id`**（don 形式など）が取れる。
- **ブラウザ** → **`POST /api/plug/sync-conversation-custom-fields`** → サーバが **`conversations.update`**（PAT / AAT）。
- **パネル有効時**も、会話開始時に **サーバ推定 IP で 1 回プリ同期**し、カスタムフィールドが空のまま残りにくくしている（`templates/base.html` の `implicitPrime`）。
- **会員ページ**から会話 ID + IP を手入力して同じ API を叩く **Snap-in なしの直接入力**もある（`/member`）。

Snap-in を足すと「**誰がいつ `conversations.update` するか**」が増えるので、**二重書き込み**と**どちらを正とするか**を先に決めると安全です。

---

## 3. Snap-in 側で検討しやすいパターン

### A. イベント駆動

- **`conversation.created`**（または組織で使える同等のトリガ）でペイロードから会話 ID を取得。
- セッション／コンテキストに **`user_ip`** が載っているなら、それを読み **`custom_fields` の API 名（例: `tnt__user_ip`）** で `conversations.update`。
- ペイロードに IP が無い場合は **別ストア**（自前 DB・前段 Webhook のキャッシュ等）と組み合わせる設計が必要。

### B. トークンと責務

- **PAT はサーバ／Snap-in 内のみ**に置き、ブラウザに近い経路に出さない運用に寄せられる。
- ブラウザ同期（このサイトの `sync-conversation-custom-fields`）と **同じ会話に対して両方が update** しないよう、**本番／検証で役割を分ける**か、**一方を無効化**する前提を決める。

### C. 二重書き込みの避け方（例）

- **本番**: Snap-in のみが `tnt__user_ip` を書く → サイト側は `DEVREV_PAT` を外すか、同期を呼ばないビルド／設定にする。
- **検証**: サイトの即時同期のみ → Snap-in はスタブまたは別 DevOrg。
- **条件分岐**: セッション属性やタグで「Snap-in 未処理」のときだけサイトが補完する（運用・実装コストは上がる）。

---

## 4. 実装・検証チェックリスト（Snap-in）

- [ ] **DevOrg** の会話スキーマで、対象フィールドの **API 名**が `tnt__user_ip` か（または別名か）を UI / API で確認済み。
- [ ] **`conversations.update` の 400** 時、`custom_schema_spec` や **tenant fragment** が原因でないか（既存の `plug_conversation_sync.py` の試行順を参考にできる）。
- [ ] **認証トークン**がその会話のパーティションに対して **update 権限**を持つか。
- [ ] **helpsite との二重 update** を避ける方針がドキュメント化されているか（このファイルまたは [conversation-user-ip-flow.md](conversation-user-ip-flow.md) に追記）。
- [ ] 本番で **PLuG の `addSessionProperties(user_ip)`** と **Snap-in の update** のどちらを「顧客 IP の正」とするか合意があるか（分析・サポートの観点）。

---

## 5. トラブル時に見る場所（このリポジトリ）

| 内容 | 場所 |
|------|------|
| update のバリアント・リトライ | `helpsite/plug_conversation_sync.py` |
| 同期 API・IP の正規化 | `helpsite/main.py`（`PlugConversationSyncBody`、`_coerce_plug_submitted_ip`） |
| PLuG・プリ同期・パネル | `templates/base.html` |
| 環境変数一覧 | `.env.example` |
| 用語とシーケンス | [conversation-user-ip-flow.md](conversation-user-ip-flow.md) |

---

## 6. 追記の仕方

採用した **Snap-in のイベント名・デプロイ先・helpsite との役割分担**が決まったら、本ファイルに **「採用パターン（日付）」** として短く追記すると、後から同じ議論を繰り返しにくくなります。
