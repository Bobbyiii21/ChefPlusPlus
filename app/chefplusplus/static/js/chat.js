const input = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const messagesWrap = document.getElementById('messagesWrap');
const emptyState = document.getElementById('emptyState');

const conversationHistory = [];

function getTheme() {
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

function avatarSrc(isTyping) {
  const theme = getTheme();
  if (isTyping) {
    return theme === 'light'
      ? '/static/img/Chat_Thinking_LightMode.gif'
      : '/static/img/Chat_Thinking_DarkMode.gif';
  }
  return theme === 'light'
    ? '/static/img/Chat_Icon_LightMode.png'
    : '/static/img/Chat_Icon_DarkMode.png';
}

function logoSrc() {
  return getTheme() === 'light'
    ? '/static/img/ChefPlusPlusLogo_LightMode.svg'
    : '/static/img/ChefPlusPlusLogo_DarkMode.svg';
}

function updateThemeImages() {
  document.querySelectorAll('.assistant-avatar img').forEach(img => {
    const isTyping = img.closest('.message.assistant')
      ?.querySelector('.message-bubble')?.classList.contains('thinking') ?? false;
    img.src = avatarSrc(isTyping);
  });
  const logo = document.getElementById('emptyStateLogo');
  if (logo) logo.src = logoSrc();
}

// Set initial logo src and update all theme-sensitive images on theme change
document.getElementById('emptyStateLogo').src = logoSrc();
new MutationObserver(updateThemeImages).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

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

function isRecipeContent(content) {
  // Convert to lowercase for case-insensitive matching
  const lowerContent = content.toLowerCase();
  
  // Recipe keywords that commonly appear in recipes
  const recipeKeywords = [
    'ingredient', 'ingredients', 'instruction', 'instructions',
    'step', 'steps', 'prepare', 'preparation',
    'cook', 'cooking', 'bake', 'baking', 'heat', 'heat', 'mix', 'combine',
    'add', 'stir', 'serve', 'serving', 'yield', 'time:', 'servings:',
    'prep time', 'cook time', 'bake time', 'total time',
    'method', 'directions', 'procedure'
  ];
  
  // Check if multiple recipe keywords are present
  let keywordCount = 0;
  for (let keyword of recipeKeywords) {
    if (lowerContent.includes(keyword)) {
      keywordCount++;
    }
  }
  
  // Consider it a recipe if we find at least 2 recipe keywords
  // This helps avoid false positives for general cooking questions
  if (keywordCount >= 3) {
    return true;
  }
  
  // Also check for recipe structure patterns
  // Look for numbered lists or bullet points that suggest steps/ingredients
  const hasNumberedList = /^\s*\d+\./m.test(content);
  const hasBulletList = /^[\s*\-•]/m.test(content);
  

  // If there's a structured list AND recipe keywords, it's likely a recipe
  if ((hasNumberedList || hasBulletList) && keywordCount >= 2) {
    return true;
  }
  
  return false;
}

function typewriterBubble(bubble, html, speed = 8) {
  const chars = [...html];
  let i = 0;
  let current = '';

  function tick() {
    // Advance by a small chunk per frame so it feels fast but smooth
    const chunkSize = Math.max(1, Math.floor(speed));
    for (let c = 0; c < chunkSize && i < chars.length; c++, i++) {
      current += chars[i];
    }
    bubble.innerHTML = current;
    messagesWrap.scrollTop = messagesWrap.scrollHeight;
    if (i < chars.length) requestAnimationFrame(tick);
  }

  requestAnimationFrame(tick);
}

function appendMessage(role, content, options = {}) {
  const isTyping = Boolean(options.isTyping);
  const referenceDownloads = options.referenceDownloads || null;
  const intent = options.intent || null;

  if (emptyState) emptyState.style.display = 'none';

  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const label = document.createElement('div');
  label.className = 'message-label';
  if (!isTyping && role === 'assistant' && intent) {
    const badge = document.createElement('span');
    badge.className = 'intent-badge';
    badge.textContent = intent;
    label.appendChild(badge);
  }

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble' + (isTyping ? ' thinking' : '');
  var formattedContent;

  if (isTyping) {
    bubble.innerHTML = '';
  } else if (role === 'assistant') {
    bubble.classList.add('markdown-body');
    formattedContent = marked.parse(content);
    typewriterBubble(bubble, formattedContent);
  } else {
    bubble.textContent = content;
  }

  // For assistant messages, wrap content in a column alongside an avatar
  if (role === 'assistant') {
    const avatar = document.createElement('div');
    avatar.className = 'assistant-avatar';
    const avatarImg = document.createElement('img');
    avatarImg.src = avatarSrc(isTyping);
    avatarImg.alt = 'Chef++ avatar';
    avatar.appendChild(avatarImg);

    const content_col = document.createElement('div');
    content_col.className = 'assistant-content-col';
    if (label.childElementCount > 0 || label.textContent) content_col.appendChild(label);
    content_col.appendChild(bubble);

    if (!isTyping && isRecipeContent(content)) {
      const actions = document.createElement('div');
      actions.className = 'message-actions';
      const saveBtn = document.createElement('button');
      saveBtn.className = 'save-recipe-btn';
      saveBtn.textContent = 'Save as Recipe';
      saveBtn.onclick = () => openSaveRecipeModal(content);
      actions.appendChild(saveBtn);
      content_col.appendChild(actions);
    }

    if (!isTyping && Array.isArray(referenceDownloads) && referenceDownloads.length > 0) {
      const bar = document.createElement('div');
      bar.className = 'reference-download-bar';
      bar.setAttribute('role', 'group');
      bar.setAttribute('aria-label', 'Download referenced documents');
      referenceDownloads.forEach((ref) => {
        if (!ref || !ref.url) return;
        const wrap = document.createElement('div');
        wrap.className = 'reference-download-bubble';
        const icon = document.createElement('span');
        icon.className = 'material-symbols-outlined reference-download-icon';
        icon.textContent = 'download';
        const link = document.createElement('a');
        link.href = ref.url;
        link.className = 'reference-download-link';
        link.textContent = ref.name || 'Download';
        wrap.appendChild(icon);
        wrap.appendChild(link);
        bar.appendChild(wrap);
      });
      if (bar.childElementCount > 0) content_col.appendChild(bar);
    }

    msg.appendChild(avatar);
    msg.appendChild(content_col);
  } else {
    msg.appendChild(label);
    msg.appendChild(bubble);
  }

  messagesWrap.appendChild(msg);
  messagesWrap.scrollTop = messagesWrap.scrollHeight;
  return msg;
}

function openSaveRecipeModal(recipeContent) {
  const modal = document.getElementById('saveRecipeModal');
  const titleInput = document.getElementById('recipeTitle');
  const contentPreview = document.getElementById('recipeContentPreview');
  const saveBtn = document.getElementById('confirmSaveRecipe');
  
  titleInput.value = '';
  
  // Parse and display markdown content
  const formattedContent = marked.parse(recipeContent);
  contentPreview.innerHTML = formattedContent;
  
  saveBtn.onclick = () => saveRecipe(recipeContent);
  modal.style.display = 'block';
}

function closeRecipeModal() {
  const modal = document.getElementById('saveRecipeModal');
  modal.style.display = 'none';
}

async function saveRecipe(recipeContent) {
  const title = document.getElementById('recipeTitle').value.trim();
  
  if (!title) {
    alert('Please enter a recipe title');
    return;
  }
  
  try {
    const res = await fetch('/recipes/save/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        title: title,
        content: recipeContent
      })
    });
    
    const data = await res.json();
    
    if (data.success) {
      alert('Recipe saved successfully!');
      closeRecipeModal();
    } else {
      alert('Error saving recipe: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    alert('Network error saving recipe: ' + err.message);
  }
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  appendMessage('user', text);

  input.value = '';
  input.style.height = 'auto';
  input.disabled = true;
  sendBtn.disabled = true;

  const MIN_THINKING_MS = 1000;
  const typingMsg = appendMessage('assistant', '', { isTyping: true });

  try {
    const [res] = await Promise.all([
      fetch('/chat/api/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: conversationHistory.length ? conversationHistory : null,
        }),
      }),
      new Promise(resolve => setTimeout(resolve, MIN_THINKING_MS)),
    ]);

    const data = await res.json();
    typingMsg.remove();

    if (data.error) {
      appendMessage('assistant', 'Sorry, something went wrong: ' + data.error);
    } else {
      appendMessage('assistant', data.reply, {
        referenceDownloads: data.reference_downloads || [],
        intent: data.intent || null,
      });
      conversationHistory.push({ role: 'user', content: text });
      conversationHistory.push({ role: 'model', content: data.reply });
    }
  } catch (err) {
    typingMsg.remove();
    appendMessage('assistant', 'Network error — please try again.');
  } finally {
    input.disabled = false;
    input.focus();
  }
}
