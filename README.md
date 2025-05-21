# LINEBOT-template

📱 LINE公式アカウント × ChatGPT のテンプレートBOT  
🍶 飲食店や居酒屋など、店舗ごとのキャラやメニューを簡単にカスタマイズして運用できます。

---

## 📦 このテンプレートでできること

- LINEでお客様と会話できるAI店主を作成
- 店舗のメニュー・接客スタイルを自由に設定可能（ファイル編集だけでOK）
- ChatGPT（OpenAI API）と連携して自然な受け答え
- 会話の文脈（3時間分）を保持して自然なやりとり
- 複数店舗展開にも対応（このテンプレートをコピーして運用）

---

## 🚀 セットアップ手順（初心者でも安心）

### 1. このテンプレートから新しいBOTを作成

GitHub上で  
👉 「**Use this template**」ボタンをクリックし、任意の名前で新しいリポジトリを作成してください。

---

### 2. 作成したリポジトリを自分のパソコンにコピー（クローン）

GitHub上の新しいリポジトリページで「**Code**」ボタンを押し、表示されるURLをコピーします。  
その後、ターミナルまたはコマンドプロンプトで以下を実行：

```bash
git clone https://github.com/あなたのユーザー名/LINEBOT-店舗名
cd LINEBOT-店舗名
🔰 例：

bash
コピーする
編集する
git clone https://github.com/sheve777/LINEBOT-showawaya
cd LINEBOT-showawaya
3. 必要なライブラリをインストール
Node.js がインストールされている状態で以下を実行：

bash
コピーする
編集する
npm install
4. .env を作成してAPIキーを設定
.env.example をコピーして .env にリネームし、各種APIキーを記入します。

bash
コピーする
編集する
cp .env.example .env
📄 .env の中身例：

env
コピーする
編集する
LINE_CHANNEL_SECRET=xxxxxxxxxxxxxxxx
LINE_CHANNEL_ACCESS_TOKEN=xxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
5. 店舗ごとのデータを設定
persona.txt：店主のキャラ・話し方・雰囲気を自由に設定

menu.json：店舗のメニューを登録（カテゴリ・品名・価格・説明）

📁 例：menu.json

json
コピーする
編集する
[
  {
    "カテゴリ": "ビール",
    "品名": "生ビール（大）",
    "価格": 500,
    "説明": "キンキンに冷えたジョッキでご提供します"
  }
]
6. アプリを起動
bash
コピーする
編集する
npm start
7. ngrokで公開し、LINE Developers にWebhook URLを設定
bash
コピーする
編集する
npx ngrok http 3000
https://xxxxx.ngrok.io/webhook を LINE Developers の Webhook URL に設定してください。

🧠 このBOTの仕組み（簡単な説明）
ユーザーからLINEでメッセージが送られる

ExpressサーバーでWebhookイベントを受信

chatgptClient.js が以下を実行：

persona.txt + menu.json を読み込む

会話履歴（3時間以内）も含めて ChatGPT に送信

ChatGPTの返答を LINE に送り返す

✅ カスタマイズポイント
ファイル	内容
persona.txt	AIの性格・話し方を自由にカスタマイズ可能
menu.json	カテゴリ・価格・説明など自由に追加・変更OK
chat/sessionManager.js	会話履歴の保持期間を変更したいときに調整
openai/chatgptClient.js	GPTのモデル（gpt-3.5, gpt-4など）を変更可能

✨ こんな使い方もできます
複数店舗をそれぞれ別キャラ・別メニューで展開

新規客・常連などで接客トーンを変える

デモ用にイベントや展示会などで設置

FlixAIと組み合わせて映像付きのマーケティングへ拡張も可能！