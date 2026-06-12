# -*- coding: utf-8 -*-
# Controller chat Mentorize.
# File ini menangani halaman pesan, polling pesan, kirim teks, kirim foto/file, dan download lampiran.

import base64

from odoo import http, fields
from odoo.http import request

from .base import MentorizeBaseController


class MentorizeChatController(MentorizeBaseController):
    # ---------- Halaman Pesan ----------
    @http.route(['/chat', '/pesan', '/mentorize/mahasiswa/chat'], type='http', auth='user', website=True, sitemap=False)
    def chat(self, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        """Menampilkan ruang pesan mentoring milik user yang sedang login."""
        room_id = int(kwargs.get('room_id') or 0)
        user = request.env.user

        domain = ['|', ('mahasiswa_user_id', '=', user.id), ('alumni_user_id', '=', user.id)]
        rooms = request.env['mentorize.roomchat'].sudo().search(domain)
        selected_room = request.env['mentorize.roomchat'].sudo().browse(room_id) if room_id else (rooms[:1] if rooms else False)

        if selected_room and not self._room_allowed(selected_room):
            selected_room = rooms[:1] if rooms else False

        # Sinkronkan lifecycle sesi saat halaman pesan dibuka agar status scheduled otomatis aktif ketika waktunya tiba.
        if selected_room and selected_room.session_id:
            self._sync_session_lifecycle(selected_room.session_id)
            selected_room.invalidate_recordset()

        other_user = self._other_user_for_room(selected_room) if selected_room else False
        can_chat = self._room_chat_open(selected_room) if selected_room else False
        values = self._layout_values('chat')
        values.update({
            'rooms': rooms,
            'selected_room': selected_room,
            'other_user': other_user,
            'can_chat': can_chat,
            'chat_lock_message': '' if can_chat else self._chat_lock_reason(selected_room),
            'current_role': self._infer_user_role(user),
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
        })
        return request.render('mentorize.page_chat', values)

    # ---------- Data Pesan untuk Polling ----------
    @http.route('/chat/data', type='http', auth='user', website=False, methods=['GET'], csrf=False)
    def chat_data(self, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect(json_response=True)
        if redirect:
            return redirect
        """Mengembalikan pesan baru dalam format JSON agar chat bisa update tanpa refresh."""
        room_id = int(kwargs.get('room_id') or 0)
        after_id = int(kwargs.get('after_id') or 0)
        room = request.env['mentorize.roomchat'].sudo().browse(room_id)

        if not room.exists() or not self._room_allowed(room):
            return self._json({'success': False, 'messages': []}, status=403)
        if room.session_id:
            self._sync_session_lifecycle(room.session_id)

        can_chat = self._room_chat_open(room)
        lock_message = '' if can_chat else self._chat_lock_reason(room)

        domain = [('room_id', '=', room.id)]
        if after_id:
            domain.append(('id', '>', after_id))

        messages = request.env['mentorize.message'].sudo().search(domain, order='id asc')
        data = []
        for msg in messages:
            attachment_url = '/chat/attachment/%s' % msg.id if msg.attachment_id else False
            data.append({
                'id': msg.id,
                'sender_id': msg.sender_id.id,
                'sender_name': msg.sender_id.name,
                'body': msg.isi_pesan or '',
                'time': self._format_user_datetime(msg.waktu_kirim, '%H:%M'),
                'is_me': msg.sender_id.id == request.env.user.id,
                'message_type': msg.message_type,
                'attachment_url': attachment_url,
                'attachment_name': msg.attachment_name or '',
                'attachment_mimetype': msg.attachment_mimetype or '',
                'attachment_size': msg.attachment_size or 0,
                'is_image': bool((msg.attachment_mimetype or '').startswith('image/')),
            })
        return self._json({
            'success': True,
            'messages': data,
            'can_chat': bool(can_chat),
            'lock_message': lock_message,
            'session_status': room.session_id.status if room.session_id else room.status,
        })

    # ---------- Kirim Pesan ----------
    @http.route('/chat/send', type='http', auth='user', website=False, methods=['POST'], csrf=False)
    def chat_send(self, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect(json_response=True)
        if redirect:
            return redirect
        """Mengirim pesan teks, foto, atau file. Lampiran dibatasi maksimal 2 MB."""
        upload = request.httprequest.files.get('attachment')
        payload = request.httprequest.get_json(silent=True) or {}

        room_id = int(kwargs.get('room_id') or payload.get('room_id') or request.httprequest.form.get('room_id') or 0)
        message = (
            kwargs.get('message')
            or payload.get('message')
            or request.httprequest.form.get('message')
            or ''
        ).strip()

        room = request.env['mentorize.roomchat'].sudo().browse(room_id)
        if not room.exists() or not self._room_allowed(room):
            return self._json({'success': False, 'error': 'Room pesan tidak valid.'}, status=403)
        if not self._room_chat_open(room):
            return self._json({'success': False, 'error': 'Pesan terkunci karena sesi belum aktif, waktu habis, atau mentoring sudah selesai.'}, status=403)

        attachment_info = False
        if upload and upload.filename:
            ok, error, attachment_info = self._read_upload(upload, self.CHAT_FILE_MIMETYPES, 'Lampiran chat')
            if not ok:
                return self._json({'success': False, 'error': error}, status=400)

        if not message and not attachment_info:
            return self._json({'success': False, 'error': 'Pesan atau lampiran wajib diisi.'}, status=400)

        message_type = 'text'
        if attachment_info:
            message_type = 'image' if attachment_info['mimetype'].startswith('image/') else 'file'

        msg = request.env['mentorize.message'].sudo().create({
            'room_id': room.id,
            'sender_id': request.env.user.id,
            'isi_pesan': message,
            'message_type': message_type,
        })

        if attachment_info:
            attachment = self._create_private_attachment(attachment_info, 'mentorize.message', msg.id)
            msg.write({
                'attachment_id': attachment.id,
                'attachment_name': attachment_info['filename'],
                'attachment_mimetype': attachment_info['mimetype'],
                'attachment_size': attachment_info['size'],
            })

        partner = room.alumni_user_id if room.mahasiswa_user_id.id == request.env.user.id else room.mahasiswa_user_id
        notif_body = '%s mengirim lampiran baru.' % request.env.user.name if attachment_info else '%s mengirim pesan baru.' % request.env.user.name
        request.env['mentorize.notification'].sudo().create_notification(
            partner,
            'Pesan baru',
            notif_body,
            notif_type='chat',
            url='/chat?room_id=%s' % room.id,
        )
        self._log_activity('chat', 'Mengirim pesan di room mentoring %s' % room.id, 'mentorize.roomchat', room.id)
        return self._json({'success': True, 'message_id': msg.id})

    # ---------- Akses Lampiran Chat ----------
    @http.route('/chat/attachment/<int:message_id>', type='http', auth='user', website=False, methods=['GET'], csrf=False)
    def chat_attachment(self, message_id, **kwargs):
        """Download/preview lampiran chat dengan pengecekan akses room."""
        msg = request.env['mentorize.message'].sudo().browse(message_id)
        if not msg.exists() or not msg.attachment_id or not self._room_allowed(msg.room_id):
            return request.not_found()

        attachment = msg.attachment_id.sudo()
        data = base64.b64decode(attachment.datas or b'')
        headers = [
            ('Content-Type', msg.attachment_mimetype or attachment.mimetype or 'application/octet-stream'),
            ('Content-Length', str(len(data))),
            ('Content-Disposition', 'inline; filename="%s"' % (msg.attachment_name or attachment.name or 'lampiran')),
        ]
        return request.make_response(data, headers=headers)
