# KOSEN Assistant for Slack

高専入試までの毎日カウントダウン、日時指定リマインダー、全国の震度5弱以上、静岡県の警報・特別警報をSlackへ通知する常時稼働向けBotです。

## 実装済み機能

- 高専入試日 `2027-02-14` を初期値に、毎日07:00以降に1回だけカウントダウン通知
- 07:00にBotが止まっていても、同日中に復旧すれば未送信分を1回通知
- `/kosen`、`/kosen set-date`、`/kosen set-time`
- 「予定・日付・時間」をSlackモーダルまたはコマンドで登録
- `/reminder add/list/today/tomorrow/edit/delete`
- Bot停止中に時刻を過ぎた予定は30分以内なら遅延通知
- SQLiteによる設定・予定・通知済みイベントの永続化
- 気象庁防災情報XMLの高頻度Atomフィードを毎分監視
- 全国で**実際に観測された最大震度5弱以上**のみ通知
- 同一地震の重複通知を抑止し、震度・M・津波コメント等の重要更新時のみ再通知
- 静岡県の気象警報・特別警報を市町村等の対象区域付きで通知
- 注意報は通知対象外
- 警報の解除通知
- Docker `restart: unless-stopped` とsystemd `Restart=always` による常時稼働構成
- `/healthz` ヘルスチェック
- pytest自動テスト

> このBotは防災情報を補助的にSlackへ転送するものです。「通知が来ない = 安全」ではありません。生命・身体の安全判断は本Botだけに依存せず、気象庁、自治体、緊急速報等の公式情報を確認してください。

## 仕組み

Slackとの通信は **Socket Mode** を使います。公開HTTPSエンドポイントを用意しなくても、Bot側からSlackへWebSocket接続してSlash Commandやモーダル操作を受け取れます。

防災情報は気象庁が公開する防災情報XML PULL型を使用します。

- 地震火山・高頻度: `https://www.data.jma.go.jp/developer/xml/feed/eqvol.xml`
- 随時・高頻度: `https://www.data.jma.go.jp/developer/xml/feed/extra.xml`
- 地震火山・長期: `https://www.data.jma.go.jp/developer/xml/feed/eqvol_l.xml`
- 随時・長期: `https://www.data.jma.go.jp/developer/xml/feed/extra_l.xml`

公式仕様:

- Slack Socket Mode: https://docs.slack.dev/tools/bolt-python/concepts/socket-mode/
- Slack Modals: https://docs.slack.dev/tools/bolt-python/concepts/opening-modals/
- 気象庁 防災情報XML PULL型: https://xml.kishou.go.jp/xmlpull.html
- 気象庁 地震情報: https://www.data.jma.go.jp/suishin/cgi-bin/catalogue/make_product_page.cgi?id=Jishin
- 気象庁 特別警報・警報・注意報: https://www.data.jma.go.jp/suishin/cgi-bin/catalogue/make_product_page.cgi?id=Keiho

## 1. Slack Appを作る

### 推奨: App Manifest

Slack App管理画面で **Create New App → From an app manifest** を選び、このリポジトリの `app_manifest.yaml` を貼り付けます。

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

自動投稿先の各チャンネルにBotを招待してください。

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
EARTHQUAKE_CHANNEL_ID=C0123456789
SHIZUOKA_ALERT_CHANNEL_ID=C0123456789
ADMIN_CHANNEL_ID=C0123456789

DATABASE_PATH=data/bot.sqlite3
KOSEN_EXAM_DATE=2027-02-14
KOSEN_NOTIFY_TIME=07:00
```

チャンネルIDはSlackで対象チャンネルの詳細を開いて確認できます。

`ADMIN_USER_IDS` を設定すると、`/kosen set-date` と `/kosen set-time` を指定ユーザーだけに制限できます。空欄なら全員が変更できます。

## 3. Dockerで24時間稼働

常時起動しているLinuxサーバー/VPS/自宅サーバーで実行します。

```bash
docker compose up -d --build
```

確認:

```bash
docker compose ps
docker compose logs -f bot
curl http://127.0.0.1:8080/healthz
```

`docker-compose.yml` は `restart: unless-stopped` のため、プロセス異常終了やホスト再起動後にDockerが起動すればBotも自動再起動します。

**重要:** GitHubリポジトリに置いただけでは24時間動作しません。24時間稼働には、24時間起動するDockerホスト/VPS等へこのコンテナを配置してください。GitHub Actionsを常駐Botのホストとしては使用しません。

## 4. systemdで24時間稼働

Dockerを使わない場合の例です。

```bash
sudo useradd --system --home /opt/kosen-slack-bot --shell /usr/sbin/nologin kosenbot
sudo mkdir -p /opt/kosen-slack-bot
sudo chown -R kosenbot:kosenbot /opt/kosen-slack-bot
```

リポジトリを `/opt/kosen-slack-bot` に配置し、仮想環境を作ります。

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

ログ:

```bash
journalctl -u kosen-slack-bot -f
```

## 5. コマンド

### 高専入試

```text
/kosen
/kosen set-date 2027-02-14
/kosen set-time 07:00
```

### リマインダー

モーダル:

```text
/reminder add
```

直接入力:

```text
/reminder add 2026-08-20 19:00 数学の過去問を解く
/reminder add today 19:00 英単語
/reminder add tomorrow 20:00 理科
/reminder add 8/20 19:00 英語
```

`M/D` は現在年として解釈します。過去日になる場合は登録を拒否します。

一覧・編集・削除:

```text
/reminder list
/reminder today
/reminder tomorrow
/reminder edit 15
/reminder delete 15
```

### 防災・状態

```text
/disaster status
/bot-status
/kosen-help
/help
```

Slackは一般的なSlash Command名の衝突を避けることを推奨しているため、`/help` が他Appと競合するワークスペースでは `/kosen-help` を使用してください。

## 6. 地震通知判定

気象庁XMLの `Intensity/Observation/MaxInt` を使用し、予測震度ではなく**観測震度**で判定します。

通知対象:

- 5弱 (`5-`)
- 5強 (`5+`)
- 6弱 (`6-`)
- 6強 (`6+`)
- 7

震度4以下は通知しません。

同じ `EventID` の情報はDBに保存し、同一内容を重複投稿しません。最大震度、M、強震地域、津波コメント等が変わった場合は更新通知します。

## 7. 静岡県警報

気象庁の「気象警報・注意報」XMLから静岡地方気象台/静岡県対象の情報を抽出します。

`警報` を含み `注意報` を含まない種類を対象とするため、以下を含む警報系情報に対応します。

- 大雨警報・大雨特別警報
- 洪水警報
- 暴風警報・暴風特別警報
- 暴風雪警報・暴風雪特別警報
- 大雪警報・大雪特別警報
- 波浪警報・波浪特別警報
- 高潮警報・高潮特別警報
- 気象庁の体系変更で追加される「危険警報」等、警報名称の情報

注意報は除外します。発表・継続・解除の状態をDBで管理し、継続だけでは繰り返し投稿しません。

### 現時点の範囲

津波警報・大津波警報、噴火警報、土砂災害警戒情報は、気象警報XMLとは電文構造が異なるため、この初版では誤通知防止を優先して自動通知対象に入れていません。追加する場合は各電文仕様に沿った専用パーサーとfixtureテストを追加してください。

## 8. データ永続化

SQLite DBは `data/bot.sqlite3` に保存されます。

保持するもの:

- 高専試験日
- 毎日の通知時刻
- 最終カウントダウン送信日
- 予定・日時・投稿先チャンネル
- 予定の通知状態
- 処理済み気象庁電文ID
- 地震EventIDと最新fingerprint
- 静岡県警報の発表状態

Dockerでは `./data:/app/data` をvolume mountしているため、コンテナ再作成後もDBが残ります。

## 9. テスト

```bash
python -m pip install ".[test]"
pytest
python -m compileall -q kosen_bot
```

テスト対象:

- 2026-08-14から2027-02-14まで184日
- 同日カウントダウン重複防止
- 前日/当日表示
- reminderの日付・時刻解析
- today/tomorrow/M/D
- 30分以内の遅延通知対象
- 古い予定のexpire
- 震度4は非通知
- 震度5弱以上は通知
- 地震EventIDの重複排除
- 5弱→6弱の更新通知
- 静岡県警報
- 注意報除外
- 他県警報除外
- 警報解除

GitHub Actionsでもpush/PRごとに同じテストを実行します。

## 10. セキュリティ/運用

- Slack Tokenは `.env` にのみ保存し、Gitへcommitしない
- Socket Modeを使うため、外部公開のSlack Request URLは不要
- XMLは `defusedxml` で解析
- JMA通信にはtimeoutを設定
- 処理済み電文IDを保存して同じXMLを繰り返し取得しない
- 気象庁障害が5分以上続いた場合のみ管理チャンネルへ通知
- Slack 429時は `Retry-After` を尊重して再試行
- Worker例外時はプロセス内で再起動し、プロセス自体が終了した場合はDocker/systemdが再起動

## 11. 気象庁公開XMLについて

気象庁は公開XMLについて、サーバーメンテナンス等で配信停止・遅延があり得ること、迅速・確実な配信を保証する用途では気象業務支援センター等への問い合わせを案内しています。そのため、本Botは防災情報の唯一の受信手段として使用しないでください。

## License

Private/personal deployment example. Add a license before redistributing as a public software package.
