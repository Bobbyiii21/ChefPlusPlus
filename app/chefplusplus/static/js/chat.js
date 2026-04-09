const input = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const messagesWrap = document.getElementById('messagesWrap');
const emptyState = document.getElementById('emptyState');
const conversationHistory = [];

function getCookie(name) {
  const cookieValue = document.cookie
    .split(';')
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${name}=`));
  return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : '';
}

// Auto-resize textarea
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 160) + 'px';
  sendBtn.disabled = input.value.trim() === '';
});

// Keyboard handling
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});

function fillSuggestion(el) {
  input.value = el.textContent.trim();
  input.dispatchEvent(new Event('input'));
  input.focus();
}

function appendMessage(role, content, isTyping = false) {
  if (emptyState) emptyState.style.display = 'none';

  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const label = document.createElement('div');
  label.className = 'message-label';
  label.textContent = role === 'user' ? 'you' : 'chef++';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble' + (isTyping ? ' thinking' : '');

  if (isTyping) {
    bubble.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  } else {
    bubble.textContent = content;
  }

  msg.appendChild(label);
  msg.appendChild(bubble);
  messagesWrap.appendChild(msg);
  messagesWrap.scrollTop = messagesWrap.scrollHeight;
  return msg;
}

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  const priorHistory = [...conversationHistory];

  appendMessage('user', text);

  // Reset input
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  // Show typing while waiting on backend.
  const typingMsg = appendMessage('assistant', '', true);
  const csrfToken = getCookie('csrftoken');

  fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken,
    },
    body: JSON.stringify({
      message: text,
      history: priorHistory,
    }),
  })
    .then(async (response) => {
      let payload = {};
      try {
        payload = await response.json();
      } catch (_e) {
        payload = {};
      }

      if (!response.ok) {
        const detail = payload.error || `Request failed (${response.status}).`;
        throw new Error(detail);
      }

      if (payload.error) {
        throw new Error(payload.error);
      }

      const replyText = (payload.reply || '').trim();
      if (!replyText) {
        throw new Error('The assistant returned an empty response.');
      }

      return replyText;
    })
    .then((replyText) => {
      conversationHistory.push(
        { role: 'user', content: text },
        { role: 'assistant', content: replyText },
      );
      appendMessage('assistant', replyText);
    })
    .catch((error) => {
      conversationHistory.push({ role: 'user', content: text });
      appendMessage('assistant', `Sorry — ${error.message}`);
    })
    .finally(() => {
      typingMsg.remove();
    });
}
