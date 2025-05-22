const fs = require('fs');
const path = require('path');
const sessionManager = require('../chat/sessionManager');
require('dotenv').config();

// ✅ 最新のOpenAI SDK（v4）を使う
const { OpenAI } = require('openai');
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

module.exports = async (event, client) => {
  const userId = event.source.userId;
  const userMessage = event.message.text;

  // personaとmenuを読み込み
  const persona = fs.readFileSync(path.join(__dirname, '../persona.txt'), 'utf8');
  const menuData = JSON.parse(fs.readFileSync(path.join(__dirname, '../menu.json'), 'utf8'));

  // メニューを読みやすい文章に整形
  const menuText = menuData.map(item => {
    const category = item.カテゴリ || '未分類';
    const name = item.品名 || item.name;
    const price = item.価格 || item.price;
    const desc = item.説明 || item.description || '説明なし';
    return `【${category}】${name}（${price}円）: ${desc}`;
  }).join('\n');

  const systemPrompt = `${persona}\n\n以下は店舗のメニューです：\n${menuText}`;

  // 過去3時間の会話履歴を取得
  const history = sessionManager.getSession(userId);

  // ChatGPTに送信するメッセージ構成
  const messages = [
    { role: 'system', content: systemPrompt },
    ...history,
    { role: 'user', content: userMessage }
  ];

  try {
    const chatCompletion = await openai.chat.completions.create({
      model: 'gpt-4',
      messages
    });

    const replyText = chatCompletion.choices[0].message.content;

    sessionManager.saveMessage(userId, 'user', userMessage);
    sessionManager.saveMessage(userId, 'assistant', replyText);

    return client.replyMessage(event.replyToken, {
      type: 'text',
      text: replyText
    });

  } catch (err) {
    console.error('❌ ChatGPT API error:', err);
    return client.replyMessage(event.replyToken, {
      type: 'text',
      text: '申し訳ありません。ただいま応答できません。少し時間をおいてお試しください。'
    });
  }
};
