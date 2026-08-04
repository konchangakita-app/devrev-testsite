# TODO（作業メモ）

> **位置づけ:** `DESIGN.md` とは別管理の、ざっくりした今後のやることリスト。  
> 内容は随時変えてよい。確定した方針は `DESIGN.md` §10 に移す。

**最終更新:** 2026-07-02

---

## 作業開始時

このリポジトリで作業を始める前に、**`DESIGN.md` とあわせて本ファイルを確認**すること。

---

## バックログ

### ユーザーの拡張（複数ドメインのユーザ）

- 複数ドメイン／事業にまたがるユーザー表現の検討・実装
- DevRev `user_ref` / アカウント階層との整合（要すり合わせ）
- スコープ・データモデルは未確定

### Phase 2 候補（連携デモ）

- **お問い合わせ** → Webhook → DevRev Ticket（`/restaurant/contact` 等。予約 CRUD は対象外）
- PLuG 会話・障害報告の Ticket 連携
- DevRev 側対応 → ステータス通知 → 業務システム反映

> 予約の作成・変更・キャンセルは PMS 内で完結。Ticket には載せない（`DESIGN.md` §3.3・P3）。

### 社内 KB — DevRev Web Crawler Job（将来）

- `/employee/` の静的 Markdown を、DevRev **Web Crawler Job API** で KB に取り込む
- KB API 直読みではなくクローラージョブで仕込む方針
- **現時点では不要**（静的 Markdown のまま運用）
- 関連スキル: `devrev-crawler-job`

---

## 完了（参考）

- ~~`/employee/` 本実装~~ — 2026-07-02 完了（`sites/employee/`）
- ~~Vercel 本番デプロイ~~ — デプロイ済
- ~~デモアクセスゲート~~ — 2026-07-02 実装（`shared/gate/`、`scripts/manage_invite_tokens.py`）

---

## メモ

- 優先順位は未固定。着手時にこのファイルと `DESIGN.md` §8 Phase を照らして決める。
- 完了したら項目を削除または「完了」にし、必要なら `DESIGN.md` を更新する。

### デモゲート運用（Agent 依頼）

```bash
# 発行
python scripts/manage_invite_tokens.py create --label "webinar"

# 一覧
python scripts/manage_invite_tokens.py list

# 無効化
python scripts/manage_invite_tokens.py revoke --id 1
```

本番の招待 URL をローカルから発行するときは `--base-url https://<project>.vercel.app` を付けてください。
