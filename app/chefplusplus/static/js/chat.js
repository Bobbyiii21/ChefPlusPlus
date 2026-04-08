const input = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const messagesWrap = document.getElementById('messagesWrap');
const emptyState = document.getElementById('emptyState');

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

  appendMessage('user', text);

  // Reset input
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  // Placeholder typing indicator — replace with real API call
  const typingMsg = appendMessage('assistant', '', true);

  setTimeout(() => {
    typingMsg.remove();
    appendMessage('assistant', '(AI response will appear here once connected to the RAG model.)');
  }, 1200);
}
