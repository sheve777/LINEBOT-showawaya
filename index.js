// index.js
require('dotenv').config();
const express = require('express');
const line = require('@line/bot-sdk');
const webhookHandler = require('./line/webhook');

const app = express();

// LINE設定
const config = {
  channelAccessToken: process.env.LINE_CHANNEL_ACCESS_TOKEN,
  channelSecret: process.env.LINE_CHANNEL_SECRET
};

// webhookルート設定
app.post('/webhook', line.middleware(config), webhookHandler(config));

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 LINEBOT is running on port ${PORT}`);
});
