const { Configuration, OpenAIApi } = require('openai');
const fs = require('fs');
const path = require('path');
const sessionManager = require('../chat/sessionManager');
require('dotenv').config();

const configuration = new Configuration({
  apiKey: process.env.OPENAI_API_KEY,
});

const openai = new OpenAIApi(configuration);

module.exports = async (event, client) => {
  const userId = event.source.userId;
  const userMessage = event.message.text;

  // === 人格とメニューの読み込み ===
  const persona = fs.readFileSync(path.join(__dirname, '../persona.txt'), 'utf8');
  const menuData = JSON.parse(fs.readFileSync(path.join(__dirname, '../menu.json'), 'utf8'));

  // メニューを自然言語に変換
  const menuText = menuData.map(item => {
    const category = item.カテゴリ || '未分類';
    const name = item.品名 || item.name;
    const price = item.価格 || item.price;
    const desc = item.説明 || item.description || '説明なし';

    return `【${category}】${name}（${price}円）: ${desc}`;
  }).join('\n');

  const systemPrompt = `${persona}\n\n以下は店舗のメニューです：\n${menuText}`;

  // === 会話履歴を取得（直近3時間） ===
  const history = sessionManager.getSession(userId);

  const messages = [
    { role: 'system', content: systemPrompt },
    ...history,
    { role: 'user', content: userMessage }
  ];

  try {
    const response = await openai.createChatCompletion({
      model: 'gpt-4',
      messages
    });

    const replyText = response.data.choices[0].message.content;

    // === 履歴に保存 ===
    sessionManager.saveMessage(userId, 'user', userMessage);
    sessionManager.saveMessage(userId, 'assistant', replyText);

    // === LINEに返信 ===
    return client.replyMessage(event.replyToken, {
      type: 'text',
      text: replyText
    });

  } catch (err) {
    console.error('❌ ChatGPT API error:', err);
    return client.replyMessage(event.replyToken, {
      type: 'text',
      text: '申し訳ありません。現在、応答できません。少し時間をおいて再度お試しください。'
    });
  }
};
