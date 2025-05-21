// line/webhook.js
const handleEvent = require('../openai/chatgptClient');

module.exports = (config) => {
  const client = new (require('@line/bot-sdk')).Client(config);

  return async (req, res) => {
    try {
      const events = req.body.events;
      const results = await Promise.all(
        events.map(event => {
          // テキストメッセージだけ処理
          if (event.type === 'message' && event.message.type === 'text') {
            return handleEvent(event, client);
          } else {
            return Promise.resolve(null);
          }
        })
      );
      res.json(results);
    } catch (err) {
      console.error('❌ Webhook error:', err);
      res.status(500).end();
    }
  };
};
