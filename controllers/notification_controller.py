# -*- coding: utf-8 -*-
# Controller ini hasil pemisahan dari main.py agar kode lebih mudah dicek dan dirawat.
# Setiap file menyimpan route sesuai kelompok fiturnya.

import base64
import json
from datetime import datetime, timedelta

from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import AccessDenied

from .base import MentorizeBaseController


class MentorizeNotificationController(MentorizeBaseController):
    # Semua method di class ini adalah route Odoo untuk fitur yang sesuai nama file.
    # ---------- notifications ----------

    # Route notifications_read: menandai semua notifikasi sebagai sudah dibaca.
    @http.route('/notifications/read', type='http', auth='user', website=False, methods=['POST'], csrf=False)
    def notifications_read(self, **kwargs):
        request.env['mentorize.notification'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('is_read', '=', False)
        ]).write({
            'is_read': True
        })

        return self._json({'success': True})

    # Route notifications_delete: hapus satu notifikasi berdasarkan ID.
    @http.route('/notifications/delete', type='http', auth='user', website=False, methods=['POST'], csrf=False)
    def notifications_delete(self, **kwargs):
        notif_id = kwargs.get('notif_id')
        if not notif_id:
            return self._json({'success': False, 'error': 'notif_id wajib diisi'}, status=400)

        try:
            notif_id = int(notif_id)
        except (ValueError, TypeError):
            return self._json({'success': False, 'error': 'notif_id tidak valid'}, status=400)

        notif = request.env['mentorize.notification'].sudo().search([
            ('id', '=', notif_id),
            ('user_id', '=', request.env.user.id),
        ], limit=1)

        if not notif:
            return self._json({'success': False, 'error': 'Notifikasi tidak ditemukan'}, status=404)

        notif.unlink()
        return self._json({'success': True})

    # Route notifications_delete_all: hapus semua notifikasi milik user yang sedang login.
    @http.route('/notifications/delete-all', type='http', auth='user', website=False, methods=['POST'], csrf=False)
    def notifications_delete_all(self, **kwargs):
        request.env['mentorize.notification'].sudo().search([
            ('user_id', '=', request.env.user.id),
        ]).unlink()

        return self._json({'success': True})
