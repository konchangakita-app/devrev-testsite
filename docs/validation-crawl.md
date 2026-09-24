# Web Crawler 検証用ページ

DevRev Web Crawler 実機検証（[devrev-validation](https://github.com/konchangakita/devrev-validation)）向けの専用パス。

## パス

- ベース: `/validation/crawl/{run_id}/`
- **デモゲート対象外**（Cookie なしのクローラーから到達可能）

| ページ | パス | 用途 |
|--------|------|------|
| 起点 | `/validation/crawl/{run_id}/` | `max_depth=0/1` の seed |
| 対照 | `.../keep` | 常時 200 |
| 404 化 | `.../for-404` | control で 404 に切替 |
| リンク除去 | `.../for-unlink` | URL は 200、seed からリンクだけ除去 |
| リダイレクト | `.../for-redirect` | 任意。control で 302 |

本文マーカー: `VALIDATION-CRAWL-{run_id}-{PAGE}`（HTML 属性 `data-validation-marker`）。

## Control API

状態は Neon（`crawl_validation_runs`）に保存。Vercel Serverless でも再デプロイ不要。

```bash
curl -sS "https://devrev-testsite.vercel.app/validation/crawl/20260924-r1/status"

curl -sS -X POST "https://devrev-testsite.vercel.app/validation/crawl/20260924-r1/control" \
  -H "Content-Type: application/json" \
  -d '{"for_404_is_gone": true}'
```

フィールド: `for_404_is_gone`, `unlink_for_unlink`, `redirect_enabled`, `redirect_target`（すべて optional）。

## 実装

- ルート: [validation/crawl/routes.py](../validation/crawl/routes.py)
- 永続化: [shared/validation/models.py](../shared/validation/models.py)
- ゲート除外: [shared/gate/middleware.py](../shared/gate/middleware.py) の `EXEMPT_PREFIXES`
