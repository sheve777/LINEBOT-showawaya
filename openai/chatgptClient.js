const fs = require('fs');
const path = require('path');
const sessionManager = require('../chat/sessionManager');
require('dotenv').config();

// OpenAI v4 SDKを使用
const { OpenAI } = require('openai');
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

module.exports = async (event, client) => {
  const userId = event.source.userId;
  const userMessage = event.message.text;

  // 店主の性格（persona）読み込み
  const persona = fs.readFileSync(path.join(__dirname, '../persona.txt'), 'utf8');

  // メニュー情報を読み込む（JSON）
  const menuData = JSON.parse(fs.readFileSync(path.join(__dirname, '../menu.json'), 'utf8'));

  // 店舗情報を読み込む（JSON）
  const storeData = JSON.parse(fs.readFileSync(path.join(__dirname, '../store.json'), 'utf8'));

  // 店舗情報のテキスト整形（カウンター・テーブル席含む）
  const storeInfo = `
店舗情報：
店名：${storeData.店名}
住所：${storeData.住所}
電話番号：${storeData.電話}
営業時間：平日 ${storeData.営業時間.平日}、土日祝 ${storeData.営業時間.土日祝}
定休日：${storeData.定休日}
席数：全${storeData.席数.カウンター + storeData.席数.テーブル}席（カウンター${storeData.席数.カウンター}席、テーブル${storeData.席数.テーブル}席）
`;

  // メニューをChatGPTが読みやすい形式に変換
  const menuText = menuData.map(item => {
    const category = item.カテゴリ || '未分類';
    const name = item.品名 || item.name;
    const price = item.価格 || item.price;
    const desc = item.説明 || item.description || '説明なし';
    return `【${category}】${name}（${price}円）: ${desc}`;
  }).join('\n');

  // システムプロンプト（GPTの前提知識）
  const systemPrompt = `
${persona}

${storeInfo}

以下は店舗のメニューです：
${menuText}
`;

  // 会話履歴（3時間分）を取得
  const history = sessionManager.getSession(userId);

  // GPTに渡すメッセージ構成
  const messages = [
    { role: 'system', content: systemPrompt },
    ...history,
    { role: 'user', content: userMessage }
  ];

  try {
    // ChatGPT APIにリクエスト（gpt-4使用）
    const chatCompletion = await openai.chat.completions.create({
      model: 'gpt-4.1-nano',
      messages
    });

    const replyText = chatCompletion.choices[0].message.content;

    // 履歴にユーザーとアシスタントのメッセージを保存
    sessionManager.saveMessage(userId, 'user', userMessage);
    sessionManager.saveMessage(userId, 'assistant', replyText);

    // LINEに返信
    return client.replyMessage(event.replyToken, {
      type: 'text',
      text: replyText
    });

  } catch (err) {
    console.error('❌ ChatGPT API error:', err);

    // エラー時のフォールバックメッセージ
    return client.replyMessage(event.replyToken, {
      type: 'text',
      text: '申し訳ありません。ただいま応答できません。少し時間をおいてお試しください。'
    });
  }
};
