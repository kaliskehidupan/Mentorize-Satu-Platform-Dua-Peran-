(function () {
  'use strict';
  if (window.__mentorizeScriptLoaded) return;
  window.__mentorizeScriptLoaded = true;

  function initMentorize() {
    if (window.__mentorizeInitialized) return;
    window.__mentorizeInitialized = true;

    function qs(sel, root) { return (root || document).querySelector(sel); }
    function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

    // ==============================
    // Kalender custom Mentorize
    // ==============================
    var activeCalendarField = null;

    function pad2(n) { return String(n).padStart(2, '0'); }
    function dateKey(date) { return date.getFullYear() + '-' + pad2(date.getMonth() + 1) + '-' + pad2(date.getDate()); }
    function monthName(year, month) {
      return new Date(year, month, 1).toLocaleDateString('id-ID', { month: 'long', year: 'numeric' });
    }
    function todayKey() { return dateKey(new Date()); }
    function parseDateKey(key) {
      var parts = (key || '').split('-').map(function (v) { return parseInt(v, 10); });
      if (parts.length !== 3 || parts.some(isNaN)) return null;
      return new Date(parts[0], parts[1] - 1, parts[2]);
    }

    function minutesOfTime(value) {
      var parts = (value || '').split(':').map(function (v) { return parseInt(v, 10); });
      if (parts.length < 2 || parts.some(isNaN)) return null;
      return (parts[0] * 60) + parts[1];
    }

    function timeFromMinutes(total) {
      total = Math.max(0, Math.min(23 * 60 + 59, total));
      return pad2(Math.floor(total / 60)) + ':' + pad2(total % 60);
    }

    function nextAvailableTime() {
      var now = new Date();
      // Tambah buffer 2 menit agar pilihan tidak langsung menjadi masa lalu saat form dikirim.
      var total = now.getHours() * 60 + now.getMinutes() + 2;
      var rounded = Math.ceil(total / 15) * 15;
      if (rounded > 23 * 60 + 45) rounded = 23 * 60 + 59;
      return timeFromMinutes(rounded);
    }

    function selectedDateTime(field) {
      if (!field || !field._mtzSelectedDate) return null;
      var panel = ensureCalendarPanel(field);
      var timeInput = qs('.mtz-calendar-time', panel);
      var selectedTime = (timeInput && timeInput.value) || '09:00';
      var parts = field._mtzSelectedDate.split('-').map(function (v) { return parseInt(v, 10); });
      var timeParts = selectedTime.split(':').map(function (v) { return parseInt(v, 10); });
      if (parts.length !== 3 || timeParts.length < 2 || parts.some(isNaN) || timeParts.some(isNaN)) return null;
      return new Date(parts[0], parts[1] - 1, parts[2], timeParts[0], timeParts[1], 0, 0);
    }

    function updateTimeConstraints(field) {
      if (!field) return;
      var panel = ensureCalendarPanel(field);
      var timeInput = qs('.mtz-calendar-time', panel);
      if (!timeInput) return;
      timeInput.setAttribute('step', '900');
      if (field._mtzSelectedDate === todayKey()) {
        var next = nextAvailableTime();
        timeInput.setAttribute('min', next);
        if (!timeInput.value || (minutesOfTime(timeInput.value) !== null && minutesOfTime(timeInput.value) < minutesOfTime(next))) {
          timeInput.value = next;
        }
      } else {
        timeInput.removeAttribute('min');
        if (!timeInput.value) timeInput.value = '09:00';
      }
    }

    function resetCalendarField(field) {
      var input = qs('input[type="hidden"]', field);
      var valueLabel = qs('.mtz-calendar-value', field);
      if (input) input.value = '';
      if (valueLabel) valueLabel.textContent = 'Belum ada jadwal dipilih';
      field._mtzSelectedDate = null;
      if (field._mtzCalendarPanel) renderCalendar(field);
    }

    function ensureCalendarPanel(field) {
      if (field._mtzCalendarPanel) return field._mtzCalendarPanel;
      var panel = document.createElement('div');
      panel.className = 'mtz-calendar-panel';
      panel.innerHTML = '' +
        '<div class="mtz-calendar-head">' +
          '<button type="button" data-mtz-cal-prev="1" aria-label="Bulan sebelumnya">‹</button>' +
          '<strong class="mtz-calendar-month"></strong>' +
          '<button type="button" data-mtz-cal-next="1" aria-label="Bulan berikutnya">›</button>' +
        '</div>' +
        '<div class="mtz-calendar-week"><span>Min</span><span>Sen</span><span>Sel</span><span>Rab</span><span>Kam</span><span>Jum</span><span>Sab</span></div>' +
        '<div class="mtz-calendar-days"></div>' +
        '<div class="mtz-calendar-time-row"><label>Jam<input type="time" class="mtz-calendar-time" value="09:00"/></label></div>' +
        '<div class="mtz-calendar-legend">' +
          '<span><i class="available"></i>Tersedia</span>' +
          '<span><i class="busy"></i>Sudah dipakai</span>' +
          '<span><i class="today"></i>Hari ini</span>' +
          '<span><i class="selected"></i>Dipilih</span>' +
        '</div>' +
        '<div class="mtz-calendar-actions">' +
          '<button type="button" class="ghost" data-mtz-cal-clear="1">Bersihkan</button>' +
          '<button type="button" class="soft" data-mtz-cal-today="1">Hari Ini</button>' +
          '<button type="button" class="primary" data-mtz-cal-pick="1">Pilih</button>' +
        '</div>' +
        '<p class="mtz-calendar-note">Tanggal merah tidak bisa dipilih karena mentor sudah memiliki sesi pada rentang 2 x 24 jam.</p>';
      field.appendChild(panel);
      field._mtzCalendarPanel = panel;
      var now = new Date();
      field._mtzYear = now.getFullYear();
      field._mtzMonth = now.getMonth();
      field._mtzBusyDates = new Set();
      return panel;
    }

    function loadBusyDates(field) {
      var busyUrl = field.getAttribute('data-busy-url') || '';
      if (!busyUrl) {
        field._mtzBusyDates = new Set();
        renderCalendar(field);
        return Promise.resolve();
      }
      field.classList.add('is-loading');
      return fetch(busyUrl, { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          field._mtzBusyDates = new Set((data && data.busy_dates) || []);
          field._mtzBusyRanges = (data && data.busy_ranges) || [];
          renderCalendar(field);
        })
        .catch(function () {
          field._mtzBusyDates = new Set();
          renderCalendar(field);
        })
        .finally(function () { field.classList.remove('is-loading'); });
    }

    function renderCalendar(field) {
      var panel = ensureCalendarPanel(field);
      var monthTitle = qs('.mtz-calendar-month', panel);
      var daysBox = qs('.mtz-calendar-days', panel);
      if (!daysBox) return;

      var year = field._mtzYear || new Date().getFullYear();
      var month = typeof field._mtzMonth === 'number' ? field._mtzMonth : new Date().getMonth();
      if (monthTitle) monthTitle.textContent = monthName(year, month);
      daysBox.innerHTML = '';

      var first = new Date(year, month, 1);
      var start = new Date(year, month, 1 - first.getDay());
      var today = todayKey();
      var selected = field._mtzSelectedDate;
      var busy = field._mtzBusyDates || new Set();

      for (var i = 0; i < 42; i++) {
        var d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
        var key = dateKey(d);
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mtz-calendar-day';
        btn.textContent = String(d.getDate());
        btn.setAttribute('data-date', key);

        if (d.getMonth() !== month) btn.classList.add('muted');
        if (key === today) btn.classList.add('today');
        if (selected === key) btn.classList.add('selected');
        if (busy.has(key)) {
          btn.classList.add('busy');
          btn.disabled = true;
          btn.title = 'Jadwal mentor sudah terpakai pada tanggal ini.';
        } else if (key < today) {
          btn.classList.add('past');
          btn.disabled = true;
        } else {
          btn.classList.add('available');
        }
        daysBox.appendChild(btn);
      }
      updateTimeConstraints(field);
    }

    function openCalendar(field) {
      if (!field) return;
      if (activeCalendarField && activeCalendarField !== field) {
        activeCalendarField.classList.remove('is-open');
      }
      activeCalendarField = field;
      ensureCalendarPanel(field);
      field.classList.add('is-open');
      loadBusyDates(field);
    }

    function selectCalendarDate(field, date) {
      if (!field || !date) return;
      field._mtzSelectedDate = date;
      updateTimeConstraints(field);
      renderCalendar(field);
    }

    function applyCalendarChoice(field) {
      if (!field || !field._mtzSelectedDate) {
        alert('Pilih tanggal yang tersedia terlebih dahulu.');
        return;
      }
      var panel = ensureCalendarPanel(field);
      var timeInput = qs('.mtz-calendar-time', panel);
      updateTimeConstraints(field);
      var selectedTime = (timeInput && timeInput.value) || '09:00';
      var chosenDateTime = selectedDateTime(field);
      if (!chosenDateTime || chosenDateTime <= new Date()) {
        alert('Jam yang dipilih sudah lewat. Pilih jam setelah waktu sekarang.');
        if (field._mtzSelectedDate === todayKey() && timeInput) timeInput.value = nextAvailableTime();
        return;
      }
      var value = field._mtzSelectedDate + 'T' + selectedTime;
      var hidden = qs('input[type="hidden"]', field);
      var label = qs('.mtz-calendar-value', field);
      if (hidden) hidden.value = value;
      if (label) {
        var d = parseDateKey(field._mtzSelectedDate);
        label.textContent = (d ? d.toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' }) : field._mtzSelectedDate) + ' pukul ' + selectedTime;
      }
      field.classList.remove('is-open');
    }

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


    function experienceRowHtml() {
      return '' +
        '<div class="mtz-experience-form-row">' +
          '<div class="mtz-form-grid two">' +
            '<label>Nama Perusahaan / Instansi<input type="text" name="exp_perusahaan" placeholder="Contoh: Shopee Indonesia"/></label>' +
            '<label>Posisi<input type="text" name="exp_posisi" placeholder="Contoh: Data Analyst"/></label>' +
            '<label>Tahun Mulai<input type="text" name="exp_tahun_mulai" placeholder="Contoh: 2020"/></label>' +
            '<label>Tahun Selesai<input type="text" name="exp_tahun_selesai" placeholder="Contoh: 2023 / Sekarang"/></label>' +
          '</div>' +
          '<label>Deskripsi Singkat<textarea name="exp_deskripsi" rows="3" placeholder="Ceritakan tanggung jawab atau pencapaian singkat."></textarea></label>' +
          '<button type="button" class="mtz-remove-experience" data-mtz-remove-experience="1">Hapus pengalaman</button>' +
        '</div>';
    }

    document.addEventListener('click', function (ev) {

      var calendarOpen = ev.target.closest('[data-mtz-calendar-open]');
      if (calendarOpen) {
        ev.preventDefault();
        openCalendar(calendarOpen.closest('.mtz-calendar-field'));
        return;
      }

      var calendarDay = ev.target.closest('.mtz-calendar-day');
      if (calendarDay && !calendarDay.disabled) {
        ev.preventDefault();
        selectCalendarDate(calendarDay.closest('.mtz-calendar-field'), calendarDay.getAttribute('data-date'));
        return;
      }

      if (ev.target.closest('[data-mtz-cal-prev]')) {
        ev.preventDefault();
        var prevField = ev.target.closest('.mtz-calendar-field');
        prevField._mtzMonth -= 1;
        if (prevField._mtzMonth < 0) { prevField._mtzMonth = 11; prevField._mtzYear -= 1; }
        renderCalendar(prevField);
        return;
      }

      if (ev.target.closest('[data-mtz-cal-next]')) {
        ev.preventDefault();
        var nextField = ev.target.closest('.mtz-calendar-field');
        nextField._mtzMonth += 1;
        if (nextField._mtzMonth > 11) { nextField._mtzMonth = 0; nextField._mtzYear += 1; }
        renderCalendar(nextField);
        return;
      }

      if (ev.target.closest('[data-mtz-cal-clear]')) {
        ev.preventDefault();
        resetCalendarField(ev.target.closest('.mtz-calendar-field'));
        return;
      }

      if (ev.target.closest('[data-mtz-cal-today]')) {
        ev.preventDefault();
        var todayField = ev.target.closest('.mtz-calendar-field');
        var now = new Date();
        todayField._mtzYear = now.getFullYear();
        todayField._mtzMonth = now.getMonth();
        todayField._mtzSelectedDate = todayKey();
        var todayPanel = ensureCalendarPanel(todayField);
        var todayTime = qs('.mtz-calendar-time', todayPanel);
        if (todayTime) todayTime.value = nextAvailableTime();
        renderCalendar(todayField);
        return;
      }

      if (ev.target.closest('[data-mtz-cal-pick]')) {
        ev.preventDefault();
        applyCalendarChoice(ev.target.closest('.mtz-calendar-field'));
        return;
      }

      if (!ev.target.closest('.mtz-calendar-field') && activeCalendarField) {
        activeCalendarField.classList.remove('is-open');
      }

      if (ev.target.closest('[data-mtz-add-experience]')) {
        ev.preventDefault();
        var list = qs('#mtz-experience-list');
        if (list) list.insertAdjacentHTML('beforeend', experienceRowHtml());
        return;
      }

      if (ev.target.closest('[data-mtz-remove-experience]')) {
        ev.preventDefault();
        var row = ev.target.closest('.mtz-experience-form-row');
        if (row) row.remove();
        return;
      }

      if (ev.target.closest('[data-mtz-scroll-request]')) {
        ev.preventDefault();
        var target = qs('#mtz-request-section');
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }

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
          var currentMentorId = reqBtn.getAttribute('data-mentor-id') || '';
          if (mentorId) mentorId.value = currentMentorId;
          if (mentorName) mentorName.value = reqBtn.getAttribute('data-mentor-name') || '';
          qsa('.mtz-calendar-field', reqModal).forEach(function (field) {
            var tpl = field.getAttribute('data-busy-url-template') || '';
            if (tpl && currentMentorId) field.setAttribute('data-busy-url', tpl.replace('__MENTOR_ID__', currentMentorId));
            resetCalendarField(field);
          });
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

    document.addEventListener('submit', function (ev) {
      var fields = qsa('.mtz-calendar-field', ev.target);
      for (var i = 0; i < fields.length; i++) {
        var hidden = qs('input[type="hidden"]', fields[i]);
        if (hidden && hidden.hasAttribute('required') && !hidden.value) {
          ev.preventDefault();
          openCalendar(fields[i]);
          alert('Pilih tanggal dan jam terlebih dahulu.');
          return;
        }
        if (hidden && hidden.value) {
          var submitted = new Date(hidden.value);
          if (!isNaN(submitted.getTime()) && submitted <= new Date()) {
            ev.preventDefault();
            openCalendar(fields[i]);
            alert('Jadwal tidak boleh memakai tanggal atau jam yang sudah lewat.');
            return;
          }
        }
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
      var fileInput = qs('#mtz-chat-attachment');

      function lastMessageId() {
        if (!messagesBox) return 0;
        var nodes = qsa('[data-message-id]', messagesBox);
        if (!nodes.length) return 0;
        return parseInt(nodes[nodes.length - 1].getAttribute('data-message-id') || '0', 10);
      }

      function scrollBottom() {
        if (messagesBox) messagesBox.scrollTop = messagesBox.scrollHeight;
      }

      function formatBytes(bytes) {
        bytes = parseInt(bytes || '0', 10);
        if (!bytes) return '';
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
      }

      function renderMessage(msg) {
        if (!messagesBox || qs('[data-message-id="' + msg.id + '"]', messagesBox)) return;
        var el = document.createElement('div');
        el.className = 'mtz-message ' + (msg.sender_id === userId ? 'me' : 'other');
        el.setAttribute('data-message-id', msg.id);

        if (msg.body) {
          var p = document.createElement('p');
          p.textContent = msg.body;
          el.appendChild(p);
        }

        if (msg.attachment_url) {
          var att = document.createElement('a');
          att.className = msg.is_image ? 'mtz-chat-image-link' : 'mtz-chat-file-link';
          att.href = msg.attachment_url;
          att.target = '_blank';
          att.rel = 'noopener';

          if (msg.is_image) {
            var img = document.createElement('img');
            img.src = msg.attachment_url;
            img.alt = msg.attachment_name || 'Gambar chat';
            att.appendChild(img);
          } else {
            att.innerHTML = '<span class="mtz-file-icon">FILE</span><strong></strong><small></small>';
            att.querySelector('strong').textContent = msg.attachment_name || 'Lampiran';
            att.querySelector('small').textContent = formatBytes(msg.attachment_size);
          }
          el.appendChild(att);
        }

        var span = document.createElement('span');
        span.textContent = msg.sender_name + ' • ' + msg.time;
        el.appendChild(span);
        messagesBox.appendChild(el);
        scrollBottom();
      }

      function poll() {
        if (!roomId) return;
        fetch('/chat/data?room_id=' + roomId + '&after_id=' + lastMessageId(), { credentials: 'same-origin' })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.success) {
              if (typeof data.can_chat !== 'undefined') {
                var currentCanChat = chatApp.getAttribute('data-can-chat') === '1';
                if (data.can_chat && !currentCanChat) {
                  window.location.reload();
                  return;
                }
                if (!data.can_chat && currentCanChat) {
                  window.location.reload();
                  return;
                }
              }
              if (data.messages) data.messages.forEach(renderMessage);
            }
          })
          .catch(function () {});
      }

      if (form && textInput) {
        form.addEventListener('submit', function (ev) {
          ev.preventDefault();
          if (chatApp.getAttribute('data-can-chat') === '0') return;
          var message = textInput.value.trim();
          var file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
          if ((!message && !file) || !roomId) return;
          if (file && file.size > 2 * 1024 * 1024) {
            alert('Ukuran file maksimal 2 MB.');
            return;
          }
          var formData = new FormData();
          formData.append('room_id', String(roomId));
          formData.append('message', message);
          if (file) formData.append('attachment', file);
          textInput.value = '';
          if (fileInput) fileInput.value = '';
          fetch('/chat/send', {
            method: 'POST',
            credentials: 'same-origin',
            body: formData
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
