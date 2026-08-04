# デモ招待リンクの確認・作成・無効化

デモサイトの「招待リンクでしか入れない」機能（デモアクセスゲート）の運用手順です。

設計の背景は [DESIGN.md §7.2](DESIGN.md#72-デモアクセスゲート招待リンク--クッキー) を参照。

---

## 仕組み（30 秒で理解）

| 項目 | 内容 |
|------|------|
| **保存先** | Neon（またはローカル SQLite）の `demo_invite_tokens` テーブル |
| **招待 URL 形式** | `https://<host>/?invite=<token>` |
| **通過後** | HttpOnly Cookie `demo_gate_session` が付与され、以降は `?invite=` なしでもアクセス可 |
| **Vercel** | ゲートは自動 ON（`VERCEL=1`）。追加 env 不要 |
| **ローカル Docker** | 既定 OFF。試すときは `.env` に `DEMO_GATE_ENABLED=true` |

**注意:** 招待トークン（`demo_invite_tokens`）と `SECRET_KEY`（`app_config` テーブル）は別物です。招待リンクの管理は本ドキュメント、セッション署名鍵は `scripts/manage_secret_keys.py` / `init_db.py` を参照。

---

## 事前準備

リポジトリルートで、ルート `.env` に `DATABASE_URL`（Neon の接続 URL）を設定してください。

```bash
cd devrev-testsite
cp .env.example .env   # 未作成の場合
# .env に DATABASE_URL を記入
```

Python 仮想環境を有効化し、依存関係をインストール済みであること。

---

## 推奨: 管理スクリプト（CLI）

`scripts/manage_invite_tokens.py` が **確認・新規作成・無効化** の正規手段です。DB を直接触るより安全です。

共通オプション（サブコマンドの**前**に置く）:

| オプション | 説明 |
|------------|------|
| `--base-url <URL>` | 招待 URL のホスト部分（未指定時は Vercel URL または `http://localhost:5020`） |
| `--path <path>` | パス（既定 `/`） |

実行例の `PYTHONPATH` は毎回付与してください。

```bash
export PYTHONPATH=sites/restaurant:sites/employee
```

### 確認（一覧・招待 URL 表示）

**Vercel 本番向け:**

```bash
python3 scripts/manage_invite_tokens.py \
  --base-url https://devrev-testsite.vercel.app \
  list
```

**ローカル向け:**

```bash
python3 scripts/manage_invite_tokens.py \
  --base-url http://localhost:5020 \
  list
```

無効化済みも含める:

```bash
python3 scripts/manage_invite_tokens.py list --all
```

出力例:

```text
---
id=1
label=webinar
status=active
created_at=2026-07-03T15:10:18.704463
last_used_at=2026-07-16T01:40:59.937475
invite_url=https://devrev-testsite.vercel.app/?invite=xxxxxxxx
```

| フィールド | 意味 |
|------------|------|
| `status=active` | 利用可能 |
| `status=revoked` | 無効化済み（この URL では入れない） |
| `last_used_at` | 最後に招待リンクが使われた日時 |

### 新規作成

```bash
python3 scripts/manage_invite_tokens.py \
  --base-url https://devrev-testsite.vercel.app \
  create --label "2026-Q3-demo"
```

`invite_url=` の行を配布用リンクとして使います。トークン文字列はランダム生成（`secrets.token_urlsafe(32)`）で、スクリプトが DB に保存します。

### 変更（実質: 無効化 + 新規発行）

トークン文字列の**直接変更は想定していません**。流出・期限切れ・用途変更時は次の手順です。

1. 古いトークンを無効化
2. 新しいトークンを発行
3. 新しい `invite_url` を配布

**ID で無効化:**

```bash
python3 scripts/manage_invite_tokens.py revoke --id 1
```

**トークン文字列で無効化:**

```bash
python3 scripts/manage_invite_tokens.py revoke --token "xxxxxxxx"
```

無効化後、既に Cookie を持っているブラウザは **次のリクエストでブロック**されます（ミドルウェアが DB を毎回検証）。

---

## Neon コンソールから直接確認（SQL）

Neon Dashboard → SQL Editor で実行できます。`DATABASE_URL` と同じ DB です。

### 有効な招待トークン一覧

```sql
SELECT id, label, token, created_at, last_used_at, revoked_at
FROM demo_invite_tokens
WHERE revoked_at IS NULL
ORDER BY id DESC;
```

### 全件（無効化済み含む）

```sql
SELECT id, label, token,
       CASE WHEN revoked_at IS NULL THEN 'active' ELSE 'revoked' END AS status,
       created_at, last_used_at, revoked_at
FROM demo_invite_tokens
ORDER BY id DESC;
```

### 招待 URL の組み立て

SQL だけではホスト名は出ません。手動で結合します。

```text
https://devrev-testsite.vercel.app/?invite=<token列の値>
```

### 直接 SQL で無効化（緊急時）

CLI が使えない場合のみ。通常は `revoke` サブコマンドを使ってください。

```sql
UPDATE demo_invite_tokens
SET revoked_at = NOW()
WHERE id = 1;
```

### 直接 SQL で新規作成（非推奨）

ランダム性・ユニーク制約のため **スクリプトの `create` を推奨**。どうしても SQL の場合は、アプリと同様に十分長いランダム文字列を自分で生成し、`token` に UNIQUE 制約違反がないことを確認してください。

---

## 環境別ベース URL

| 環境 | ベース URL | ゲート |
|------|------------|--------|
| Vercel 本番 | `https://<project>.vercel.app` | ON（自動） |
| ローカル Docker | `http://localhost:5020` | OFF（既定） |
| ローカル（ゲート ON 時） | `http://localhost:5020` | `.env` で `DEMO_GATE_ENABLED=true` |

スクリプト未指定時の自動判定:

- `DEMO_GATE_BASE_URL` があれば優先
- Vercel では `VERCEL_URL` から `https://...` を生成
- それ以外は `http://localhost:5020`

---

## よくある運用シーン

| シーン | 手順 |
|--------|------|
| 今の招待リンクを知りたい | `list`（`--base-url` で環境を指定） |
| 新しいデモ用リンクを配りたい | `create --label "用途"` |
| リンクが漏れた | `revoke --id N` → `create` で再発行 |
| デプロイ後に入れない | `DATABASE_URL` が Neon を指しているか、`init_db.py` 済みか、有効トークンがあるかを確認 |
| Cookie ありで入れる人と、リンク必須の人 | 正常動作。無効化で全員ブロック可能 |

---

## 関連ファイル

| パス | 役割 |
|------|------|
| `scripts/manage_invite_tokens.py` | 招待トークン CLI |
| `shared/gate/models.py` | `DemoInviteToken` モデル |
| `shared/gate/tokens.py` | 発行・無効化・URL 組み立て |
| `shared/gate/middleware.py` | ゲートミドルウェア |
| `sites/restaurant/init_db.py` | テーブル作成（`demo_invite_tokens` 含む） |

---

## クイックリファレンス

```bash
export PYTHONPATH=sites/restaurant:sites/employee
BASE="https://devrev-testsite.vercel.app"

# 確認
python3 scripts/manage_invite_tokens.py --base-url "$BASE" list

# 新規
python3 scripts/manage_invite_tokens.py --base-url "$BASE" create --label "my-demo"

# 無効化
python3 scripts/manage_invite_tokens.py revoke --id 1
```
