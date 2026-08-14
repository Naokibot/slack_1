# KOSEN Assistant for Slack

高専入試までの毎日カウントダウンと、日時指定の予定リマインダーをSlackで使うためのBotです。

防災監視機能は削除済みです。現在は学習・予定管理に機能を絞っています。

## 実装済み機能

- 高専入試日 `2027-02-14` を初期値に、毎日07:00以降に1回だけカウントダウン通知
- 07:00にBotが止まっていても、同日中に復旧すれば未送信分を1回通知
- `/kosen`
- `/kosen set-date YYYY-MM-DD`
- `/kosen set-time HH:MM`
- 「予定・日付・時間」をSlackモーダルから登録
- `/reminder add YYYY-MM-DD HH:MM 予定` で直接登録
- `today` / `tomorrow` / `M/D` の簡易日付指定
- `/reminder list`
- `/reminder today`
- `/reminder tomorrow`
- `/reminder edit ID`
- `/reminder delete ID`
- Bot停止中に予定時刻を過ぎた場合、30分以内なら遅延通知
- SQLiteによる設定・予定の永続化
- Docker `restart: unless-stopped`
- systemd `Restart=always`
- `/healthz` ヘルスチェック
- pytest自動テスト

## 仕組み

Slackとの通信は **Socket Mode** を使用します。公開HTTPSエンドポイントを用意しなくても、Bot側からSlackへWebSocket接続してSlash Commandやモーダル操作を受け取れます。

現在の実装はPython + Slack Bolt + SQLiteです。

## 1. Slack Appを作る

Slack App管理画面で **Create New App → From an app manifest** を選び、このリポジトリの `app_manifest.yaml` を使用してください。

### Socket Mode

1. Slack Appの **Socket Mode** をONにする
2. App-Level Tokenを作成する
3. Tokenのscopeに `connections:write` を付ける
4. `xapp-...` で始まるトークンを控える

### OAuth

Bot Token Scopes:

- `chat:write`
- `commands`

ワークスペースへAppをインストールし、`xoxb-...` のBot Tokenを取得します。

### チャンネルへBotを追加

高専カウントダウンとリマインダーの投稿先チャンネルにBotを招待してください。

## 2. 環境変数

```bash
cp .env.example .env
```

`.env` を編集します。

```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

COUNTDOWN_CHANNEL_ID=C0123456789
REMINDER_CHANNEL_ID=C0123456789

DATABASE_PATH=data/bot.sqlite3
KOSEN_EXAM_DATE=2027-02-14
KOSEN_NOTIFY_TIME=07:00
REMINDER_POLL_SECONDS=15
HEALTH_PORT=8080
```

`ADMIN_USER_IDS` を設定すると、`/kosen set-date` と `/kosen set-time` を指定ユーザーだけに制限できます。空欄なら全員が変更できます。

## 3. Dockerで24時間稼働

常時起動しているLinuxホストやVPSで実行する場合:

```bash
docker compose up -d --build
```

確認:

```bash
docker compose ps
docker compose logs -f bot
curl http://127.0.0.1:8080/healthz
```

`docker-compose.yml` は `restart: unless-stopped` を設定しているため、Botプロセスの異常終了やホスト再起動後にも自動復旧できます。

GitHubリポジトリへ置くだけではBotは常時実行されません。24時間稼働させる場合は、常時実行できるホストまたは対応するサーバーレス基盤が必要です。

## 4. systemdで24時間稼働

Dockerを使わない場合:

```bash
sudo useradd --system --home /opt/kosen-slack-bot --shell /usr/sbin/nologin kosenbot
sudo mkdir -p /opt/kosen-slack-bot
sudo chown -R kosenbot:kosenbot /opt/kosen-slack-bot
```

リポジトリを `/opt/kosen-slack-bot` に配置し、仮想環境を作成します。

```bash
cd /opt/kosen-slack-bot
python3.12 -m venv .venv
.venv/bin/pip install .
cp .env.example .env
```

サービス登録:

```bash
sudo cp deploy/kosen-slack-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kosen-slack-bot
sudo systemctl status kosen-slack-bot
```

## 5. 高専入試コマンド

```text
/kosen
/kosen set-date 2027-02-14
/kosen set-time 07:00
```

`/kosen` は現在日付と試験日の差から残り日数を毎回計算します。

試験前日は専用メッセージ、試験当日は当日用メッセージを表示します。試験終了後は毎日の自動通知を停止します。

## 6. リマインダー

モーダルを開く:

```text
/reminder add
```

モーダルには以下の3項目があります。

- 予定
- 日付
- 時間

直接入力:

```text
/reminder add 2026-08-20 19:00 数学の過去問を解く
/reminder add today 19:00 英単語
/reminder add tomorrow 20:00 理科
/reminder add 8/20 19:00 英語
```

一覧・編集・削除:

```text
/reminder list
/reminder today
/reminder tomorrow
/reminder edit 15
/reminder delete 15
```

予定は日時が近い順に表示します。過去の完了済みリマインダーは通常の一覧には表示しません。

## 7. Bot状態

```text
/bot-status
```

高専カウントダウン、予定リマインダー、DBの状態を表示します。

使い方:

```text
/kosen-help
/help
```

## 8. データ

SQLite DBの標準保存先:

```text
data/bot.sqlite3
```

保存される主な情報:

- 高専入試日
- 毎日のカウントダウン通知時刻
- 最終カウントダウン通知日
- リマインダー
- リマインダー通知状態

Botを再起動しても予定は保持されます。

## 9. テスト

```bash
python -m pip install ".[test]"
pytest
python -m compileall -q kosen_bot
```

テスト対象:

- 高専入試までの日数計算
- 試験前日・当日・試験終了後
- JSTの日付処理
- リマインダー登録
- today / tomorrow / M/D
- 予定一覧
- 30分以内の遅延通知対象
- 古い予定の失効
- SQLite永続化

## 10. 防災機能について

以前実装していた以下の機能は削除しました。

- 全国の震度5弱以上の地震監視
- 静岡県の警報・特別警報監視
- 気象庁XMLポーリング
- `/disaster` コマンド
- 地震・警報用DB状態
- 防災用環境変数

このBotは現在、防災情報の取得・監視・通知を行いません。
