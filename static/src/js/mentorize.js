(function () {
  'use strict';
  if (window.__mentorizeScriptLoaded) return;
  window.__mentorizeScriptLoaded = true;

  function initMentorize() {
    if (window.__mentorizeInitialized) return;
    window.__mentorizeInitialized = true;

    function qs(sel, root) { return (root || document).querySelector(sel); }
    function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

    function closeDropdowns(exceptId) {
      qsa('.mtz-dropdown').forEach(function (el) {
        if (el.id !== exceptId) el.classList.remove('show');
      });
    }

    function setRole(root, role) {
      if (!role) return;
      qsa('.mtz-role-tabs button', root || document).forEach(function (b) {
        b.classList.toggle('active', b.getAttribute('data-role') === role);
      });
      qsa('input[name="role"]', root || document).forEach(function (input) { input.value = role; });
      var label = qs('#mtz-identity-label', root || document);
      var identityInput = qs('#mtz-identity-input', root || document);
      if (label) label.textContent = role === 'alumni' ? 'KAPA / ID Alumni' : 'NIM';
      if (identityInput) identityInput.placeholder = role === 'alumni' ? 'Masukkan KAPA alumni' : 'Masukkan NIM mahasiswa';
    }

    // Inisialisasi role awal dari hidden input.
    qsa('[data-mtz-role-tabs]').forEach(function (box) {
      var form = box.closest('form') || document;
      var input = qs('input[name="role"]', form);
      setRole(form, input ? input.value : 'mahasiswa');
    });

    document.addEventListener('click', function (ev) {
      var roleBtn = ev.target.closest('.mtz-role-tabs button[data-role]');
      if (roleBtn) {
        ev.preventDefault();
        setRole(roleBtn.closest('form') || document, roleBtn.getAttribute('data-role'));
        return;
      }

      var toggle = ev.target.closest('[data-mtz-toggle]');
      if (toggle) {
        ev.preventDefault();
        var id = toggle.getAttribute('data-mtz-toggle') === 'notifications' ? 'mtz-notifications' : 'mtz-user-menu';
        var menu = qs('#' + id);
        if (menu) {
          var willShow = !menu.classList.contains('show');
          closeDropdowns(id);
          menu.classList.toggle('show', willShow);
        }
        return;
      }

      if (!ev.target.closest('.mtz-dropdown') && !ev.target.closest('[data-mtz-toggle]')) {
        closeDropdowns();
      }

      if (ev.target.closest('[data-mtz-open-logout]')) {
        ev.preventDefault();
        var modal = qs('#mtz-logout-modal');
        if (modal) modal.classList.add('show');
      }
      if (ev.target.closest('[data-mtz-close-logout]')) {
        ev.preventDefault();
        var logoutModal = qs('#mtz-logout-modal');
        if (logoutModal) logoutModal.classList.remove('show');
      }
      if (ev.target.matches('.mtz-modal-backdrop')) {
        ev.target.classList.remove('show');
      }

      var reqBtn = ev.target.closest('[data-mtz-open-request]');
      if (reqBtn) {
        ev.preventDefault();
        var reqModal = qs('#mtz-request-modal');
        if (reqModal) {
          var mentorId = qs('#mtz-request-mentor-id', reqModal);
          var mentorName = qs('#mtz-request-mentor-name', reqModal);
          if (mentorId) mentorId.value = reqBtn.getAttribute('data-mentor-id') || '';
          if (mentorName) mentorName.value = reqBtn.getAttribute('data-mentor-name') || '';
          reqModal.classList.add('show');
        }
      }
      if (ev.target.closest('[data-mtz-close-modal]')) {
        ev.preventDefault();
        var modalClose = ev.target.closest('.mtz-modal-backdrop') || qs('#mtz-request-modal');
        if (modalClose) modalClose.classList.remove('show');
      }

      if (ev.target.closest('[data-mtz-read-notifications]')) {
        ev.preventDefault();
        fetch('/notifications/read', { method: 'POST', credentials: 'same-origin' })
          .then(function () {
            qsa('.mtz-notif-item.unread').forEach(function (item) { item.classList.remove('unread'); });
            qsa('.mtz-notif-badge').forEach(function (badge) { badge.remove(); });
          })
          .catch(function () {});
      }
    });

    // Chat auto-update tanpa refresh manual.
    var chatApp = qs('#mtz-chat-app');
    if (chatApp) {
      var roomId = parseInt(chatApp.getAttribute('data-room-id') || '0', 10);
      var userId = parseInt(chatApp.getAttribute('data-user-id') || '0', 10);
      var messagesBox = qs('#mtz-chat-messages');
      var form = qs('#mtz-chat-form');
      var textInput = qs('#mtz-chat-text');

      function lastMessageId() {
        if (!messagesBox) return 0;
        var nodes = qsa('[data-message-id]', messagesBox);
        if (!nodes.length) return 0;
        return parseInt(nodes[nodes.length - 1].getAttribute('data-message-id') || '0', 10);
      }

      function scrollBottom() {
        if (messagesBox) messagesBox.scrollTop = messagesBox.scrollHeight;
      }

      function renderMessage(msg) {
        if (!messagesBox || qs('[data-message-id="' + msg.id + '"]', messagesBox)) return;
        var el = document.createElement('div');
        el.className = 'mtz-message ' + (msg.sender_id === userId ? 'me' : 'other');
        el.setAttribute('data-message-id', msg.id);
        var p = document.createElement('p');
        p.textContent = msg.body;
        var span = document.createElement('span');
        span.textContent = msg.sender_name + ' • ' + msg.time;
        el.appendChild(p);
        el.appendChild(span);
        messagesBox.appendChild(el);
        scrollBottom();
      }

      function poll() {
        if (!roomId) return;
        fetch('/chat/data?room_id=' + roomId + '&after_id=' + lastMessageId(), { credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.success && data.messages) data.messages.forEach(renderMessage);
          })
          .catch(function () {});
      }

      if (form && textInput) {
        form.addEventListener('submit', function (ev) {
          ev.preventDefault();
          if (chatApp.getAttribute('data-can-chat') === '0') return;
          var message = textInput.value.trim();
          if (!message || !roomId) return;
          textInput.value = '';
          fetch('/chat/send', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ room_id: roomId, message: message })
          }).then(function (r) { return r.json(); }).then(function (data) {
            if (data && data.success) poll();
            else if (data && data.error) alert(data.error);
          }).catch(function () {});
        });
      }

      scrollBottom();
      poll();
      setInterval(poll, 1400);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMentorize, { once: true });
  } else {
    initMentorize();
  }
})();
