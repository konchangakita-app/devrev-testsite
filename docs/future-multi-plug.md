# 将来: マルチ PLuG チャット対応

> **ステータス:** 未実装（DevRev マルチ PLuG リリース待ち）  
> **設計方針の正:** [DESIGN.md](./DESIGN.md) §6.2

## 背景

| 時期 | DevRev の制約 | 本リポジトリの方針 |
|------|---------------|-------------------|
| **現行** | 1 DevRev 組織 = **PLuG app_id 1 つ** | ルート `.env` の `DEVREV_PLUG_APP_ID` / AAT を全サイトで共有 |
| **将来** | **マルチ PLuG チャット**（複数 widget / app_id per org） | サイトごとに app_id・AAT を分離。会話・Session replay 設定の混在を防ぐ |

現行方式は製品制約に合わせた暫定ではなく、**意図した現行アーキテクチャ**とする。マルチ PLuG 公開後に §6.2 の手順で拡張する。

## 予約している環境変数（未使用・コメントのみ）

ルート `.env` に、将来次の **サイト別キー**を追加できるように命名を予約している。

| 共通（現行で使用） | 将来のサイト別上書き（例） |
|-------------------|---------------------------|
| `DEVREV_PLUG_APP_ID` | `DEVREV_PLUG_APP_ID__restaurant`, `DEVREV_PLUG_APP_ID__employee` |
| `DEVREV_APPLICATION_ACCESS_TOKEN` | `DEVREV_APPLICATION_ACCESS_TOKEN__restaurant`, `...__employee` |
| `DEVREV_PAT` | `DEVREV_PAT__restaurant`, `DEVREV_PAT__employee`（必要なら） |

- 区切りは **`__`（ダブルアンダースコア）**
- `<site_slug>` はパスと一致: `restaurant`, `employee`, `it-sier`, `retail`
- **サイト別が未設定**のときは共通キーにフォールバック（後方互換）

## コード上の準備（実装済・現行はフォールバックのみ）

`shared/devrev/plug_env.py` の `resolve_site_env()` が上記の解決順を実装している。

各サイトの `SITE_SLUG`（例: `restaurant`）を渡し、PLuG 初期化前に解決する:

```python
from shared.devrev.plug_env import resolve_site_env

app_id = resolve_site_env("DEVREV_PLUG_APP_ID", "restaurant", settings.devrev_plug_app_id)
```

現行では `DEVREV_PLUG_APP_ID__*` を設定しなければ、従来どおり共通 `DEVREV_PLUG_APP_ID` のみが使われる。

## マルチ PLuG リリース後のアップデート手順

1. **DevRev 管理画面**でサイト用途ごとに PLuG app を作成（顧客向け / 社員向け 等）
2. ルート `.env`（および Vercel Environment Variables）にサイト別キーを追加
3. `sites/<name>/` の PLuG 初期化が `resolve_site_env` 経由か確認（未対応サイトは実装）
4. `docs/DESIGN.md` §6 の app_id 行を「サイト別推奨」に更新
5. §10 決定ログに移行完了を記録
6. デモ確認: 会話が意図した PLuG app に紐づくこと、Session replay 設定が混在しないこと

### 想定タスク（Phase 2 以降）

- [ ] `/employee/` 実装時に `SITE_SLUG=employee` で PLuG 連携
- [ ] テンプレート / `addSessionProperties` に `site=<slug>` を統一付与
- [ ] `.env.example` のコメントアウト済みサイト別キーを有効化例として追記
- [ ] Vercel env のドキュメント更新（共通 + サイト別の併記）

## 参照

- [DESIGN.md §6 DevRev / PLuG 方針](./DESIGN.md#6-devrev--plug-方針)
- [DESIGN.md §6.2 マルチ PLuG への拡張（将来）](./DESIGN.md#62-マルチ-plug-への拡張将来)
- `shared/devrev/plug_env.py`
