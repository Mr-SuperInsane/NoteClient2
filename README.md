![](https://raw.githubusercontent.com/Mr-SuperInsane/NoteClient2/refs/heads/main/NoteClientHeader.png)

Python から **note に記事を投稿するための非公式ライブラリ**です。  
Markdown で記述した記事を、画像・アイキャッチ・有料エリアを含めて投稿できます。

本ライブラリはPlaywrightによるスクレイピングと内部APIを組み合わせることで高速かつ安定した投稿処理を実現しています。

## 概要

**NoteClient2** は、2023年10月に公開されたNoteClient（初期バージョン）の後継ライブラリです。

初期バージョンではSeleniumを用いたブラウザ操作ベースの実装を採用していましたが、

- 動作速度が遅い
- 記事内への画像挿入ができない
- アイキャッチ画像が既存画像のみ
- 有料記事に対応していない

といった制約がありました。

しかし、**NoteClient2**では設計を全面的に見直し、

- ログインのみPlaywrightを使用
- それ以外の処理はすべてnoteの内部APIを直接利用
- セッション（Cookie）をローカルに保存し再利用

という構成に変更することで、**実用レベルの投稿速度と機能性**を実現しています。


## 主な機能
### 記事投稿
- Markdownファイルから記事を投稿
- 下書き保存 / 公開の切り替え対応
- ハッシュタグ指定対応

### 画像アップロード
- ローカル画像を記事内に挿入
- ローカル画像をアイキャッチ画像として設定

### 有料記事対応
- Markdown内に `<pay>` タグを記述することで、それ以降の内容を有料エリアとする
- 金額の指定も可能

### マガジン指定
- 複数マガジン指定対応

### セッション再利用
- ログイン後のCookieをJSONファイルに保存
- Cookieが有効な限り再ログインを省略
- 高速かつ安定した連続投稿が可能


## インストール

```bash
pip install NoteClient2
````

### Playwright のセットアップ（必須）

本ライブラリではPlaywrightを使用します。
インストール後、必ず以下を実行してください。

```bash
playwright install
```


## 基本的な使い方

```python
from NoteClient2 import NoteClient2
from dotenv import load_dotenv

load_dotenv()

# .envファイルを利用して機密情報を安全に取り扱ってください
EMAIL = os.getenv("email")
PASSWORD = os.getenv("password")
USER_URL_ID = os.getenv("user_url_id")

client = NoteClient2(
    email=EMAIL,
    password=PASSWORD,
    user_urlname=USER_URL_ID
)

result = client.publish(
    title="Note Client2 テスト記事",
    md_file_path="article.md",
    eyecatch_path="eyecatch.png",
    hashtags=["Python", "note"], 
    price=300,
    magazine_key=["mxxxxxxxxxxxx"], 
    is_publish=True
)

if result["success"]:
    print("投稿成功:", result["url"])
else:
    print("エラー:", result["error"])
```

## Markdown による記事の書き方

### 基本構文

```md
# 見出し1
## 見出し2
### 見出し3

通常の文章です。

- リスト
- リスト

> 引用文
```

### インライン装飾

```md
**太字**
*斜体*
~~打ち消し~~
[リンク](https://example.com)
```

---

### 画像の挿入

```md
![画像の説明](path/to/image.png)
```

* ローカルパスを指定してください
* 自動的にアップロードされ、記事内に挿入されます

---

### 目次の挿入

```md
<toc>
```

目次が挿入されます。

---

### 有料記事の書き方

```md
ここまでは無料で読めます。

<pay>

ここからは有料エリアです。
```

#### ルール

* `<pay>` は **1行のみ・1回のみ**
* `<pay>` 以前 → 無料エリア
* `<pay>` 以降 → 有料エリア


## publish() の主な引数

| 引数名           | 説明                  |
| ------------- | ------------------- |
| title         | 記事タイトル              |
| md_file_path  | Markdown ファイルのパス    |
| eyecatch_path | アイキャッチ画像（任意）        |
| hashtags      | ハッシュタグのリスト          |
| price         | 有料記事の価格（0で無料）       |
| magazine_key  | マガジンキーのリスト          |
| is_publish    | True で公開、False で下書き |

## エラーハンドリング

本ライブラリでは `raise` を使用せず、
**戻り値として辞書型で結果を返します**。

```python
{
    "success": False,
    "error": "エラーメッセージ",
    "detail": {...}
}
```

これにより、呼び出し側で柔軟な制御が可能です。

## 注意事項

* 本ライブラリは **非公式** です
* note の仕様変更により動作しなくなる可能性があります
* 利用は自己責任でお願いします
* 過度な自動投稿・スパム行為は推奨しません

---

## 関連リンク

* 初期バージョン（v1）
  [https://github.com/Mr-SuperInsane/NoteClient](https://github.com/Mr-SuperInsane/NoteClient)

* PyPI
  [https://pypi.org/project/NoteClient/](https://pypi.org/project/NoteClient/)

---

## ライセンス

[INSANE License](https://github.com/Mr-SuperInsane/NoteClient2/blob/main/LICENSE)