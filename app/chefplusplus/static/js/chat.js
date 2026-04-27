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

function appendMessage(role, content, isTyping = false) {
  if (emptyState) emptyState.style.display = 'none';

  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const label = document.createElement('div');
  label.className = 'message-label';
  label.textContent = role === 'user' ? 'you' : 'chef++';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble' + (isTyping ? ' thinking' : '');
  var formattedContent;

  if (isTyping) {
    bubble.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
  } else if (role === 'assistant') {
    bubble.classList.add('markdown-body');
    formattedContent = marked.parse(content);
    bubble.innerHTML = formattedContent;
  } else {
    bubble.textContent = content;
  }

  msg.appendChild(label);
  msg.appendChild(bubble);
  
  // Add save recipe button only for assistant messages that contain recipes
  if (role === 'assistant' && !isTyping && isRecipeContent(content)) {
    const actions = document.createElement('div');
    actions.className = 'message-actions';
    
    const saveBtn = document.createElement('button');
    saveBtn.className = 'save-recipe-btn';
    saveBtn.textContent = 'Save as Recipe';
    saveBtn.onclick = () => openSaveRecipeModal(content);
    
    actions.appendChild(saveBtn);
    msg.appendChild(actions);
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
