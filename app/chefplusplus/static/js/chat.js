const input = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const messagesWrap = document.getElementById('messagesWrap');
const emptyState = document.getElementById('emptyState');

const conversationHistory = [];

marked.setOptions({
  breaks: true,
  gfm: true,
});

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
  } else if (role === 'assistant') {
    bubble.classList.add('markdown-body');
    bubble.innerHTML = marked.parse(content);
  } else {
    bubble.textContent = content;
  }

  msg.appendChild(label);
  msg.appendChild(bubble);
  messagesWrap.appendChild(msg);
  messagesWrap.scrollTop = messagesWrap.scrollHeight;
  return msg;
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  appendMessage('user', text);

  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  const typingMsg = appendMessage('assistant', '', true);

  try {
    const res = await fetch('/chat/api/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: conversationHistory.length ? conversationHistory : null,
      }),
    });

    const data = await res.json();
    typingMsg.remove();

    if (data.error) {
      appendMessage('assistant', 'Sorry, something went wrong: ' + data.error);
    } else {
      appendMessage('assistant', data.reply);
      conversationHistory.push({ role: 'user', content: text });
      conversationHistory.push({ role: 'model', content: data.reply });
    }
  } catch (err) {
    typingMsg.remove();
    appendMessage('assistant', 'Network error — please try again.');
  }
}
