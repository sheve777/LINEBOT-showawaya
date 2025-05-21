const sessionStore = {};

const MAX_SESSION_TIME_MS = 1000 * 60 * 60 * 3; // 3時間

function now() {
  return new Date().getTime();
}

function cleanOldMessages(messages) {
  const threshold = now() - MAX_SESSION_TIME_MS;
  return messages.filter(msg => msg.timestamp >= threshold);
}

function getSession(userId) {
  if (!sessionStore[userId]) {
    sessionStore[userId] = [];
  }

  sessionStore[userId] = cleanOldMessages(sessionStore[userId]);

  return sessionStore[userId].map(msg => ({
    role: msg.role,
    content: msg.content
  }));
}

function saveMessage(userId, role, content) {
  if (!sessionStore[userId]) {
    sessionStore[userId] = [];
  }

  sessionStore[userId].push({
    role,
    content,
    timestamp: now()
  });

  sessionStore[userId] = cleanOldMessages(sessionStore[userId]);
}

module.exports = {
  getSession,
  saveMessage
};
