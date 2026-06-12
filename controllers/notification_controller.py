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

    # Route notifications_read: menangani request web untuk fitur ini.
    @http.route('/notifications/read', type='http', auth='user', website=False, methods=['POST'], csrf=False)
    def notifications_read(self, **kwargs):
        request.env['mentorize.notification'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('is_read', '=', False)
        ]).write({
            'is_read': True
        })

        return self._json({'success': True})


