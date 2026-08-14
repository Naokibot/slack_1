# KOSEN Assistant for Slack

Slack Developer Sandbox と Run On Slack Infrastructure (ROSI) 上で動く、高専入試カウントダウン＋予定リマインダーです。

## 構成

- TypeScript / Deno Slack SDK
- Slack Datastore
- Scheduled Trigger
- Slack scheduled messages
- Link Trigger + OpenForm
- 自宅サーバー / VPS / Docker / SQLite / Socket Mode は不要

## 初期値

- 高専入試日: `2027-02-14`
- 通知時刻: `07:00`
- タイムゾーン: `Asia/Tokyo`

初回は「高専カウントダウン設定」トリガーから、試験日・通知時刻・通知先チャンネルを保存してください。

## 必要なもの

- Slack Developer Sandbox
- Slack CLI
- Deno
- Git

## チェック

```bash
deno task check
```

`fmt`, `lint`, `deno check`, `deno test` をまとめて実行します。

## デプロイ

リポジトリのルートで:

```bash
slack login
slack deploy
```

デプロイ先には Developer Sandbox を選択してください。

## 操作用トリガー

デプロイ後に以下を作成します。

```bash
slack trigger create --trigger-def triggers/kosen_settings.ts
slack trigger create --trigger-def triggers/kosen_status.ts
slack trigger create --trigger-def triggers/reminder_add.ts
slack trigger create --trigger-def triggers/reminder_list.ts
slack trigger create --trigger-def triggers/reminder_edit.ts
slack trigger create --trigger-def triggers/reminder_delete.ts
```

表示されたURLをSlackチャンネルのブックマーク等に登録すると使いやすくなります。

## 機能

### 高専入試カウントダウン

- 毎日指定時刻に残り日数を投稿
- 前日・当日は専用メッセージ
- 試験終了後は投稿停止
- 設定変更時はrevisionを更新し、古いScheduled Triggerによる二重投稿を防止

### リマインダー

- 予定、日付、時刻、通知先をSlackフォームから登録
- 一覧表示
- 編集
- 削除
- Slack Datastoreへ保存
- 予約可能範囲外の遠い予定はDatastoreで待機し、日次処理で予約可能範囲へ入った時点でSlack scheduled messageへ移行

## 重要

このリポジトリはROSI専用です。旧Python/Socket Mode版の実行ファイルやDocker構成は含めません。
