// AssureX Help Assistant - chat widget
function toggleChat() {
  var p = document.getElementById('axChatPanel');
  p.style.display = p.style.display === 'flex' ? 'none' : 'flex';
  if (p.style.display === 'flex') {
    if (!document.getElementById('axChatMessages').hasChildNodes()) {
      addMsg('assistant', 'Hi! I can help you navigate AssureX — how to add products, submit claims, check status, or understand your claim results.\n\n(Note: I provide guidance only — claim decisions are made by the AI evaluation system and human reviewers.)');
    }
    document.getElementById('axChatInput').focus();
  }
}

function addMsg(role, text) {
  var msgs = document.getElementById('axChatMessages');
  var d = document.createElement('div');
  d.className = 'ax-chat-msg ax-chat-msg--' + role;

  // format: **bold** → <b>, *italic* → <em>, `code` → <code>,
  // - item → <li>, line breaks → <br>. Escape HTML first for safety.
  var escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  var formatted = escaped
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/\n/g, '<br>');
  // wrap consecutive <li> in <ul>
  formatted = formatted.replace(/(<li>.*?<\/li>(<br>)?)+/g, function (m) {
    return '<ul>' + m.replace(/<br>/g, '') + '</ul>';
  });

  d.innerHTML = formatted;
  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
}

function sendChat(ev) {
  ev.preventDefault();
  var input = document.getElementById('axChatInput');
  var msg = input.value.trim();
  if (!msg) return false;
  input.value = '';
  addMsg('user', msg);

  var msgs = document.getElementById('axChatMessages');
    var loading = document.createElement('div');
  loading.className = 'ax-chat-loading';
  loading.innerHTML = '<span></span><span></span><span></span>';
  msgs.appendChild(loading);
  msgs.scrollTop = msgs.scrollTop = msgs.scrollHeight;

  // CSRF token from the meta tag (same protection as all forms)
  var tokenMeta = document.querySelector('meta[name="csrf-token"]');
  var token = tokenMeta ? tokenMeta.content : '';

  fetch('/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': token
    },
    body: 'message=' + encodeURIComponent(msg)
  })
  .then(function (r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  })
  .then(function (data) {
    loading.remove();
    addMsg('assistant', data.response || 'Sorry, I could not process that.');
  })
  .catch(function (err) {
    loading.remove();
    addMsg('assistant', 'Connection issue (' + err.message + '). ' +
      'Your claims are always available on the My Claims page.');
  });
  return false;
}