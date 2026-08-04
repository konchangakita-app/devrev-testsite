# KON レストラン予約デモ（`sites/restaurant`）

モノレポ内の **お客様向けレストラン予約サイト**です。FastAPI + Neon（PostgreSQL）/ SQLite、DevRev PLuG 対応。

**アクセス URL:** `http://localhost:5020/restaurant/`（リポジトリルートから起動した場合）

起動方法はリポジトリルートの [README.md](../../README.md) を参照してください。

## 起動（単体デバッグ・非推奨）

通常はリポジトリルートの `docker compose up` を使います。サイト単体で動かす場合:

```bash
cd sites/restaurant
pip install -r requirements.txt
python init_db.py
uvicorn helpsite.main:app --reload --host 0.0.0.0 --port 5021
# → http://localhost:5021/  （url_prefix 未マウント時はルート直下）
```

## 自動作成されるテストユーザー

初回起動時に DB に **デモユーザー**が無ければ作成されます（冪等）。

**一般会員（予約・マイ予約・お問い合わせ）**

| 項目 | 値 |
|------|-----|
| ユーザー名 | `demo` |
| メール | `demo+mbr@helpsite.local` |
| パスワード | `demo1234` |

**管理者（ユーザー管理・全予約管理）** — `/restaurant/admin/login`

| 項目 | 値 |
|------|-----|
| ユーザー名 | `konadmin` |
| メール | `konadmin+admin@helpsite.local` |
| パスワード | `konadmin1234` |

**本番環境ではこの固定アカウントを使わないでください。** ローカル／検証用デモ専用です。

## PLuG 検証用 API

- **会話の user_ip（チャット開始 → カスタムフィールド）** … 用語（`user_ip` と API 名 `tnt__user_ip`）、処理の流れ、将来の Snap-in との役割分担のメモは **[docs/conversation-user-ip-flow.md](docs/conversation-user-ip-flow.md)** を参照してください。
- **`GET /api/user-context`** … `addSessionProperties` 用 JSON。デモ用（`city`, `region`, `demo_source`, `demo_region`）に加え、**セッション向けの `user_ip`**（`X-Forwarded-For` 等から推定）を返します。`templates/base.html` は **`init` 直後（after_init）と `ON_PLUG_WIDGET_READY`（on_ready）** の両方で fetch して送信します。
- **`POST /api/plug/sync-conversation-custom-fields`** … ブラウザが会話 ID を送り、サーバが **`conversations.update`** で会話のカスタムフィールド（既定は **`tnt__user_ip`**）に IP を書きます。要 `DEVREV_PAT`（または権限の足りる AAT）と CSRF。
- **Web セッション記録（Session replay）** … `DEVREV_PLUG_ENABLE_SESSION_RECORDING=true` のとき、`plugSDK.init` に [session_recording_options](https://devrev.ai/docs/plug/session-recording) を渡します（[Customer Support Agent / Session recording の説明](https://support.devrev.ai/en-US/devrev/article/HWipyCxT-customer-support-agent-overview)）。組織の **Settings → Plug** で Session Replays 等が有効なこと、プライバシー要件に合わせマスキングを調整してください。
- **Docker Compose** はリポジトリルートの `docker-compose.yml` を使用（ポート **5020**）。

## 環境変数

ルートの **`.env.example` → `.env`** に `DATABASE_URL`・`DEVREV_*` 等を記入します（全サイト共通）。  
Vercel には同じキー名で Environment Variables に写します。

| 変数 | 置き場所 | 説明 |
|------|----------|------|
| `DATABASE_URL` | ルート `.env` | Neon 接続文字列。未設定時は SQLite |
| `SECRET_KEY` | ルート `.env` | セッション署名 |
| `DEVREV_PLUG_APP_ID` | ルート `.env` | PLuG の `app_id` |
| `DEVREV_PLUG_ENABLE_SESSION_RECORDING` | ルート `.env` | `true` で Web セッション記録を有効化。既定は `false`。 |
| `DEVREV_APPLICATION_ACCESS_TOKEN` | ルート `.env` | 任意。会員ログイン時に RevUser セッショントークンを発行。**未設定なら匿名 PLuG**。 |
| `DEVREV_ACCOUNT_REF` | ルート `.env` | 任意。`auth-tokens.create` の `rev_info.account_ref`。 |
| `DEVREV_WORKSPACE_REF` | ルート `.env` | 任意。同上 `workspace_ref`。 |
| `ADMIN_API_KEY` | ルート `.env` | 任意。管理者 API 参照用 `ps_` 形式キー。 |

## エンドポイント概要（マウント時は `/restaurant` プレフィックス付き）

- `GET /restaurant/` — トップ（KON デモレストラン案内）
- `GET /contact` — お問い合わせフォーム
- `POST /api/contact` — お問い合わせ送信（デモ: サーバログに記録、メール送信なし）
- `GET /reserve` — オンライン予約フォーム（要ログイン・ハリボテ）
- `POST /api/reserve` — 予約送信（PMS / DB に永続化）
- `GET /member/reservations` — マイ予約（要会員ログイン）
- `POST /api/my/reservations/{id}/cancel` — 自分の予約キャンセル（デモ）
- `GET /admin/login` — 管理者ログイン（会員ログインとは別）
- `POST /auth/admin/login` / `POST /auth/admin/logout` — 管理者セッション
- `GET /admin` — 管理ダッシュボード（要管理者ログイン）
- `GET /admin/reservations` — 予約管理（要管理者ログイン）
- `GET /admin/users` — ユーザー管理（要管理者ログイン）
- `POST /api/admin/reservations/{id}/status` — 予約状態のデモ更新
- `GET /member` — 会員専用（要ログイン）
- `POST /auth/login` / `POST /auth/register` / `POST /auth/logout` — JSON（CSRF トークン必須）
- `GET /health` — ヘルスチェック
- `GET /api/admin/user?devrev_revuser_id=...` — PetStore 互換。`Authorization: Bearer` に `ps_`（ユーザーの API キーまたは `ADMIN_API_KEY`）、または `ey`（`DEVREV_APPLICATION_ACCESS_TOKEN` と一致する組織トークン想定）を付与。管理者または本人のみ参照可。

## 参考

- Demo-PetStore の Docker／PLuG 読み込みパターン
- [DevRev PLuG ドキュメント](https://devrev.ai/docs/plug)
- [会話 user_ip の流れ（チャット開始 → `conversations.update`）](docs/conversation-user-ip-flow.md)
- [Snap-in 開発メモ（user_ip / 二重書き込み / チェックリスト）](docs/snap-in-development-notes.md)
- 既存会員 DB を変えずに会員 ID を `user_ref` にする設計メモ: [docs/design-devrev-existing-members.md](docs/design-devrev-existing-members.md)
