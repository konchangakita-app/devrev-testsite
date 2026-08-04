# devrev-samplesite

KON グループ（架空）を題材にした **DevRev サンプルサイト群**のモノレポです。

| URL | 内容 |
|-----|------|
| `/` | ポータル（サイト一覧） |
| `/restaurant/` | お客様向けレストラン予約デモ |
| `/employee/` | 社内向けヘルプ（記事・検索・社員 PLuG） |

## 設計方針

**開発の唯一の設計方針:** [docs/DESIGN.md](docs/DESIGN.md)

## 環境変数

**すべてリポジトリルートの `.env` に集約**（ローカル・Vercel・Docker 共通）。

| 置き場所 | 内容 |
|----------|------|
| **`.env`**（ルート） | `DATABASE_URL`, `SECRET_KEY`, `DEVREV_PLUG_APP_ID`, `DEVREV_APPLICATION_ACCESS_TOKEN` 等 |

```bash
cp .env.example .env
# .env に DATABASE_URL・DevRev 設定を記入
# Vercel には同じキー名で Environment Variables に写す
```

既存の `sites/restaurant/.env` は移行期間のみ読み込まれます（非推奨）。

マルチ PLuG 対応の予定は [docs/future-multi-plug.md](docs/future-multi-plug.md) を参照。

## デモアクセスゲート

限定公開デモ向け。詳細は [docs/DESIGN.md](docs/DESIGN.md) §7.2。

**Vercel では追加の環境変数は不要です**（`VERCEL` / `VERCEL_URL` は自動設定され、ゲート ON・招待 URL 生成に使われます）。

ローカルでゲートを試すときだけ `.env` に `DEMO_GATE_ENABLED=true` を設定してください。

```bash
# トークン発行（Agent 依頼または手動）
python scripts/manage_invite_tokens.py create --label "webinar"

# 一覧・無効化
python scripts/manage_invite_tokens.py list
python scripts/manage_invite_tokens.py revoke --id 1
```

## ローカル起動

### Docker Compose（推奨）

```bash
docker compose up --build
# → http://localhost:5020/
```

### Python（開発用）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=sites/restaurant:sites/employee python sites/restaurant/init_db.py
PYTHONPATH=sites/restaurant:sites/employee uvicorn app.main:app --reload --host 0.0.0.0 --port 5020
```

## Vercel デプロイ

1. GitHub に push したうえで [Vercel](https://vercel.com) からリポジトリをインポート（Root Directory は空のまま）
2. **Environment Variables** にルート `.env` の値を写す（`DATABASE_URL`, `SECRET_KEY`, `DEVREV_*` 等）
3. 初回デプロイ前に Neon へ `init_db.py` を実行済みであること（ローカルからで可）
4. デプロイ後: `https://<project>.vercel.app/`（ポータル）、`/restaurant/`（レストラン）、`/employee/`（社内ヘルプ）

エントリは `api/index.py`（Mangum）。詳細は [docs/DESIGN.md](docs/DESIGN.md) §7。

## リポジトリ構成

```
.env.example         # 全環境変数テンプレート（共通）
api/index.py         # Vercel Serverless エントリ
vercel.json
app/                 # ルート FastAPI（マウント・ポータル）
portal/              # GET / ポータル
sites/restaurant/    # レストラン予約デモ
sites/employee/      # 社内向けヘルプ
docs/DESIGN.md       # 設計方針（唯一の正）
```

レストランサイトの詳細は [sites/restaurant/README.md](sites/restaurant/README.md)。
