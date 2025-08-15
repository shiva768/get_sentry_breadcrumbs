# Sentryパンくずリスト・データ抽出スクリプト

このスクリプトは、Sentryの特定Issueを調査し、関連する全てのイベントを取得して、各イベントのパンくずリスト（breadcrumbs）を検索します。ユーザーが提供した正規表現を使い、パンくずリスト内のログから特定のデータを抽出するように設計されています。

## 主な機能

-   SentryのIssue IDを指定して、関連する全てのイベントを取得（APIのページネーションに対応）
-   各パンくずリストのJSON全体を、ユーザーが指定した正規表現で検索
-   正規表現の**最初のキャプチャグループ `()`** にマッチした部分を抽出して表示
-   APIのレートリミットを避けるため、設定可能な待機時間を導入
-   コマンドライン引数、環境変数、`.env`ファイルによる柔軟な設定が可能

---

## セットアップ

1.  **依存ライブラリのインストール**

    仮想環境の利用を推奨します。

    ```bash
    # 仮想環境の作成と有効化（任意ですが推奨）
    python -m venv venv
    source venv/bin/activate

    # 必要なライブラリをインストール
    pip install -r requirements.txt
    ```

2.  **環境変数の設定**

    プロジェクトのルートディレクトリに `.env` ファイルを作成してください。このファイルは `.gitignore` に記載されているため、Gitリポジリにはコミットされません。

    ```
    # .env ファイル
    YOUR_SENTRY_API_TOKEN="YOUR_TOKEN_HERE"
    SENTRY_ORGANIZATION="your-organization-slug"      # --organizationでも設定可能
    SENTRY_PROJECT="your-project-slug"     # --projectでも設定可能
    ```

    - **`YOUR_SENTRY_API_TOKEN`**: (必須) あなたのSentry APIトークン。Sentryの *Settings > Developer Settings > New Internal Integration* から発行できます。`Event: Read` の権限が必要です。
    - **`SENTRY_ORGANIZATION`**: (任意) Sentryの組織スラッグ。
    - **`SENTRY_PROJECT`**: (任意) Sentryのプロジェクトスラッグ。

---

## 使い方

このスクリプトは、2つの必須引数 `issue_id` と `regex` を取ります。

### コマンド体系

```bash
python get_sentry_breadcrumbs.py <issue_id> "<regex>" [オプション]
```

### 重要: 正規表現パラメータについて

有効なPythonの正規表現を渡す必要があります。特定の値を抽出するには、**キャプチャグループ `()`** を使用してください。スクリプトは、最初に見つかったキャプチャグループの中身を出力します。

シェルの特殊な解釈を避けるため、正規表現はダブルクォート `""` で囲むことを強く推奨します。

### 引数

-   `issue_id`: (必須) 調査したいSentryのIssue ID。
-   `regex`: (必須) 検索に使用する正規表現。抽出したい部分をキャプチャグループ `()` で囲ってください。

### オプション

-   `--organization <slug>`: Sentryの組織スラッグ。環境変数 `SENTRY_ORGANIZATION` より優先されます。
-   `--project <slug>`: Sentryのプロジェクトスラッグ。環境変数 `SENTRY_PROJECT` やIssueからの自動取得より優先されます。
-   `--limit <number>`: 処理するイベント数を制限します。`0`を指定すると全てのイベントを処理します（デフォルト: `0`）。
-   `-h`, `--help`: ヘルプメッセージを表示します。

### 使用例

**例1: SQLクエリからIDを抽出する**

SQL文の中から `` `user_id` = 12345 `` のような部分を探す場合：

```bash
python get_sentry_breadcrumbs.py 1234567890 "`user_id`\s*=\s*(\d+)"
```
- **正規表現**: `` "`user_id`\s*=\s*(\d+)" ``
- **キャプチャグループ**: `(\d+)` が数字の部分を捉えます。
- **出力**: `12345`

**例2: キー・バリュー形式からIDを抽出する**

`user_id: 12345` のような部分を探す場合：

```bash
python get_sentry_breadcrumbs.py 1234567890 "user_id:\s*(\d+)"
```
- **正規表現**: `"user_id:\s*(\d+)"`
- **キャプチャグループ**: `(\d+)` がラベルの後の数字を捉えます。
- **出力**: `12345`

**例3: URLを抽出する**

`url: "https://example.com"` のような部分を探す場合：

```bash
python get_sentry_breadcrumbs.py 1234567890 "url: \"(https?:\/\/[^\"]+)\"
```
- **正規表現**: `"url: \"(https?:\/\/[^\"]+)\"`
- **キャプチャグループ**: `(https?:\/\/[^\"]+)` がクォート内のURLを捉えます。
- **出力**: `https://example.com`