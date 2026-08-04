# PLuGチャット開始時のIPアドレス記録フロー

このドキュメントでは、ヘルプサイトでPLuGチャットを開始した際に、DevRevの会話カスタムフィールド `user_ip` へIPアドレスを自動記録する仕組みをわかりやすく解説

---

## 登場人物

1. **ユーザーのブラウザ**（JavaScript実行環境）
2. **PLuG SDK**（DevRevが提供するJavaScriptライブラリ、ブラウザ内で動作）
3. **ヘルプサイトのバックエンドサーバ**（FastAPI、あなたが管理）
4. **DevRev API**（DevRevのクラウドサービス）

---

## フロー詳細

### **ステップ1: ページ読み込み時のIPアドレス取得**

**誰が**: ユーザーのブラウザ  
**どこに対して**: ヘルプサイトのバックエンドサーバ  
**API**: `GET /api/user-context`

```
[ユーザーのブラウザ] → [ヘルプサイトのバックエンドサーバ]
                     GET /api/user-context
```

- **目的**: サーバー側でリクエスト元のIPアドレスを推定
- **返却データ例**:
  ```json
  {
    "user_ip": "203.0.113.45",
    "city": "ApiTokyo",
    "region": "api-kanto"
  }
  ```

---

### **ステップ2: PLuG SDKの初期化**

**誰が**: ユーザーのブラウザ  
**どこに対して**: PLuG SDK（ブラウザ内）  
**API**: `plugSDK.init({ app_id: "...", ... })`

```
[ユーザーのブラウザ] → [PLuG SDK（ブラウザ内）]
                     plugSDK.init()
```

- **目的**: チャットウィジェットを画面に表示する準備

---

### **ステップ3: セッション属性の送信**

**誰が**: ユーザーのブラウザ  
**どこに対して**: PLuG SDK（ブラウザ内）  
**API**: `plugSDK.addSessionProperties({ user_ip: "203.0.113.45", ... })`

```
[ユーザーのブラウザ] → [PLuG SDK（ブラウザ内）]
                     addSessionProperties({ user_ip: "...", city: "..." })
```

- **目的**: ステップ1で取得したIPアドレスなどをPLuG SDKに渡す
- **注意**: この時点ではDevRevサーバーに送信されません（SDK内部で保持）

> **PLuG SDKの内部動作**: この後、PLuG SDKが自動的にDevRev APIサーバーと通信し、セッション属性をDevRevクラウドに送信します。

---

### **ステップ4: ユーザーがチャットを開始**

**誰が**: ユーザー  
**操作**: PLuGウィジェットの「チャットを開始」ボタンをクリック

```
[ユーザー] → [PLuG SDK（ブラウザ内）]
          チャット開始操作
```

---

### **ステップ5: 会話IDの通知**

**誰が**: PLuG SDK  
**どこに対して**: ユーザーのブラウザ（イベントリスナー）  
**API**: `onEvent({ type: "ON_CONVERSATION_START", conversation_id: "CONV-123" })`

```
[PLuG SDK（ブラウザ内）] → [ユーザーのブラウザ]
                       onEvent({ conversation_id: "CONV-123" })
```

- **目的**: 作成された会話のIDをブラウザのJavaScriptに通知
- **会話IDの形式**: `CONV-123` または `don:identity:dvr-...:conversation/123`

---

### **ステップ6: 会話カスタムフィールドへの同期リクエスト（自動）**

**誰が**: ユーザーのブラウザ  
**どこに対して**: ヘルプサイトのバックエンドサーバ  
**API**: `POST /api/plug/sync-conversation-custom-fields`

```
[ユーザーのブラウザ] → [ヘルプサイトのバックエンドサーバ]
                     POST /api/plug/sync-conversation-custom-fields
                     {
                       "conversation_id": "CONV-123",
                       "user_ip": "203.0.113.45",  // 省略可能
                       "csrf_token": "..."
                     }
```

- **目的**: 会話IDとIPアドレスをサーバーに送信
- **タイミング**: 会話開始直後に自動実行
- **user_ip省略時**: サーバーがリクエスト元IPを自動判定

---

### **ステップ7: DevRev APIへの書き込み**

**誰が**: ヘルプサイトのバックエンドサーバ  
**どこに対して**: DevRev API  
**API**: `POST https://api.devrev.ai/conversations.update`

```
[ヘルプサイトのバックエンドサーバ] → [DevRev API]
                                 POST /conversations.update
                                 {
                                   "id": "CONV-123",
                                   "custom_fields": {
                                     "tnt__user_ip": "203.0.113.45"
                                   }
                                 }
```

- **目的**: DevRevの会話レコードにIPアドレスを記録
- **認証**: `DEVREV_PAT`（Personal Access Token）を使用
- **カスタムフィールド名**: 環境変数で設定可能（既定: `tnt__user_ip`）

---

### **ステップ8: 完了通知**

**誰が**: ヘルプサイトのバックエンドサーバ  
**どこに対して**: ユーザーのブラウザ  
**レスポンス**: `{ "ok": true, "user_ip": "203.0.113.45" }`

```
[ヘルプサイトのバックエンドサーバ] → [ユーザーのブラウザ]
                                 { "ok": true, "user_ip": "..." }
```

- **目的**: 同期が成功したことをブラウザに通知
- **ブラウザ側の処理**: デバッグモード時はコンソールにログ出力

---

## フロー全体図

```
┌─────────────┐
│ユーザー操作 │ページを開く
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│1. IP取得             │
│[ブラウザ] → [ヘルプサイトサーバ]│
│GET /api/user-context │
└──────┬───────────────┘
       │ user_ip: "203.0.113.45"
       ▼
┌──────────────────────┐
│2. PLuG初期化         │
│[ブラウザ] → [PLuG SDK]│
│plugSDK.init()        │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│3. セッション属性設定  │
│[ブラウザ] → [PLuG SDK]│
│addSessionProperties()│
└──────┬───────────────┘
       │
       ▼
┌─────────────┐
│ユーザー操作 │チャット開始
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│4. 会話ID通知         │
│[PLuG SDK] → [ブラウザ]│
│onEvent(CONV-123)     │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│5. 同期リクエスト      │
│[ブラウザ] → [ヘルプサイトサーバ]│
│POST /sync-...        │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│6. DevRev更新         │
│[ヘルプサイトサーバ] → [DevRev API]│
│conversations.update  │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│7. 完了               │
│IPアドレスがDevRevの  │
│会話に記録されました   │
└──────────────────────┘
```

---

## 重要ポイント

### **セキュリティ上の理由でバックエンドサーバーを経由**

- ブラウザから直接DevRev APIを呼ぶことは**できません**
- 理由: `DEVREV_PAT`（認証トークン）をブラウザに公開できない
- そのため、**ヘルプサイトのバックエンドサーバーが代理で実行**

### **IPアドレスの取得方法**

| 取得元 | 説明 |
|--------|------|
| **X-Forwarded-For** | プロキシ・CDN経由時に元のクライアントIPを含むヘッダー |
| **request.client.host** | 直接接続時のIPアドレス |
| **ユーザー入力** | オプション機能で手動入力可能（`DEVREV_PLUG_PROMPT_USER_IP=true`） |

### **自動同期のタイミング**

- `DEVREV_PLUG_PROMPT_USER_IP=false`（既定）: 会話開始直後に**即座に自動同期**
- `DEVREV_PLUG_PROMPT_USER_IP=true`: 左下パネルでIPを確認してから同期

---

## 環境変数

| 変数 | 役割 |
|------|------|
| `DEVREV_PAT` | `conversations.update` の認証トークン（推奨） |
| `DEVREV_APPLICATION_ACCESS_TOKEN` | 代替認証トークン（権限が足りる場合） |
| `DEVREV_CONVERSATION_CUSTOM_FIELD_USER_IP` | カスタムフィールドのAPI名（既定: `tnt__user_ip`） |
| `DEVREV_PLUG_PROMPT_USER_IP` | `true` でIP確認パネル表示、`false` で自動同期のみ |

---

## デバッグモード

URLに `?plug_debug=1` を付けると、ブラウザのコンソールに詳細なログが出力されます。

```
http://localhost:5020/?plug_debug=1
```

以下の情報が確認できます：

- `/api/user-context` のレスポンス
- `addSessionProperties` の送信データ
- `onEvent` で受信した会話ID
- `/api/plug/sync-conversation-custom-fields` のリクエスト・レスポンス

---

## 関連ドキュメント

- [conversation-user-ip-flow.md](conversation-user-ip-flow.md) - 技術的な詳細
- [snap-in-development-notes.md](snap-in-development-notes.md) - Snap-in開発時の注意点
- [DevRev PLuG ドキュメント](https://devrev.ai/docs/plug)
