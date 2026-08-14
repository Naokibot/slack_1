# KOSEN Assistant for Slack

高専入試カウントダウンと予定リマインダーを、**Run On Slack Infrastructure (ROSI)** 上で動かすSlack Workflow Appです。

自宅サーバー、VPS、Docker、Python常駐プロセス、SQLite、Socket Modeは使いません。Slack Developer Sandboxで約6か月使う個人向け構成を想定しています。

## 機能

- 高専入試日までの残り日数を毎日自動投稿
- 初期想定: `2027-02-14`、毎日 `07:00`（Asia/Tokyo）
- 試験日・通知時刻・通知先チャンネルをSlackフォームから変更
- 同じ日にカウントダウンを二重投稿しない
- 予定、日付、時刻、通知先をSlackフォームから登録
- 予定一覧（all / today / tomorrow）
- 予定の編集・削除
- 予定はSlack Datastoreに保存
- 100日以内の予定はSlack Scheduled Messageとして予約
- 100日より先の予定はDatastoreで待機し、日次処理が100日以内になった時点で自動予約
- 予定の閲覧・編集・削除は登録した本人に限定

## 必要なもの

- Slack Developer Sandbox
- Slack CLI
- Deno
- Git

Bot用サーバーやクラウドVMは不要です。

## 1. リポジトリを取得

```powershell
git clone https://github.com/Naokibot/slack_1.git
cd slack_1
```

## 2. ローカル検証

```powershell
deno task check
```

このタスクはDenoの整形、lint、型チェック、単体テストを実行します。

## 3. Slack CLIでSandboxへログイン

```powershell
slack login
```

表示された `/slackauthticket ...` をDeveloper Sandbox内のSlackへ貼り付け、表示されたchallenge codeをターミナルへ入力します。

ログイン確認:

```powershell
slack auth list
```

## 4. ROSIへデプロイ

```powershell
slack deploy
```

対象を聞かれたらDeveloper Sandboxを選択します。デプロイ後はPCを24時間起動しておく必要はありません。

## 5. 操作用Link Triggerを作成

```powershell
slack trigger create --trigger-def triggers/kosen_settings.ts
slack trigger create --trigger-def triggers/kosen_status.ts
slack trigger create --trigger-def triggers/reminder_add.ts
slack trigger create --trigger-def triggers/reminder_list.ts
slack trigger create --trigger-def triggers/reminder_edit.ts
slack trigger create --trigger-def triggers/reminder_delete.ts
```

各コマンドが返したURLを使うチャンネルへ貼るか、チャンネルのブックマークへ登録してください。

## 6. 最初の設定

「高専カウントダウン設定」のLink Triggerを開き、次を入力します。

- 試験日: `2027-02-14`
- 通知時刻: `07:00`
- 通知先: カウントダウンを投稿したいチャンネル

初回設定を行ったユーザーが設定オーナーになります。以後、高専カウントダウンの全体設定を変更できるのはそのユーザーだけです。

## 予定リマインダー

「予定を追加」から次を入力します。

- 予定名
- 日付 (`YYYY-MM-DD`)
- 時刻 (`HH:MM`)
- 通知先チャンネル

登録後に予定IDが表示されます。編集・削除にはこのIDを使います。「予定を見る」でIDを再確認できます。

## アーキテクチャ

```text
Slack Developer Sandbox
  ├─ Link Trigger + OpenForm
  ├─ Workflow
  ├─ Custom Function (Deno / TypeScript)
  ├─ Slack Datastore
  ├─ Scheduled Trigger     -> 毎日の高専カウントダウン / 予定保守
  └─ Scheduled Message     -> 指定日時の予定通知
```

### Datastore

`settings`
- 高専入試日
- 通知時刻
- 通知チャンネル
- 設定オーナー
- Scheduled Trigger ID
- revision
- 最終送信日

`reminders`
- 予定ID
- 予定名
- 日付・時刻
- 通知チャンネル
- 登録ユーザー
- 状態
- Slack Scheduled Message ID

## 重要な運用上の注意

- 通知先がプライベートチャンネルの場合は、アプリがそのチャンネルへ投稿できる状態にしてください。
- Developer Sandboxの有効期間を超えて使う場合は、別のSandboxまたは利用可能なSlackプランへの移行が必要です。
- `slack deploy` はSlackアカウントの認証が必要なため、リポジトリのCIだけでは本番Sandboxへの実デプロイまでは行いません。

## 開発チェック

GitHub Actionsとローカルの両方で次を実行します。

```powershell
deno task check
```

GitHub Actionsが成功しているコミットをデプロイしてください。
