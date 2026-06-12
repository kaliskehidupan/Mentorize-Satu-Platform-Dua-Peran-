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


class MentorizeMentorController(MentorizeBaseController):
    # Semua method di class ini adalah route Odoo untuk fitur yang sesuai nama file.
    # ---------- mentor, request, calendar ----------
    # Route mentors: menangani request web untuk fitur ini.
    @http.route(['/mentors', '/mentorize/mahasiswa/cari-mentor'], type='http', auth='user', website=True, sitemap=False)
    def mentors(self, **kwargs):
        if self._infer_user_role(request.env.user) == 'alumni':
            return request.redirect('/alumni/dashboard')

        mahasiswa = self._ensure_profile('mahasiswa')

        if not mahasiswa.profile_complete:
            return request.redirect('/profile/setup')

        query = (kwargs.get('q') or '').strip()
        auto_match = kwargs.get('match') == '1' or not query
        Alumni = request.env['mentorize.alumni'].sudo()

        if query:
            base_mentors = Alumni.search([
                ('user_id.active', '=', True),
                ('availability', '!=', 'offline'),
                '|', '|', '|', '|',
                ('user_id.name', 'ilike', query),
                ('pekerjaan', 'ilike', query),
                ('deskripsi', 'ilike', query),
                ('skill_ids.name', 'ilike', query),
                ('minat_ids.name', 'ilike', query),
            ])
        else:
            base_mentors = Alumni.search([
                ('user_id.active', '=', True),
                ('availability', '!=', 'offline'),
            ])

        ranked = self._rank_mentors(mahasiswa, base_mentors)
        mentors = [item['mentor'] for item in ranked] if auto_match or query else self._recommend_mentors(mahasiswa, limit=30)
        match_context = self._mentor_match_context(ranked)

        values = self._layout_values('mentors')
        values.update({
            'mahasiswa': mahasiswa,
            'mentors': mentors,
            'q': query,
            'match_active': auto_match,
            'match_scores': match_context['match_scores'],
            'match_reasons': match_context['match_reasons'],
            'match_labels': match_context['match_labels'],
            'today': fields.Date.context_today(request.env.user),
            'max_date': fields.Date.context_today(request.env.user) + timedelta(days=90),
            'today_min': fields.Date.to_string(fields.Date.context_today(request.env.user)) + 'T00:00',
            'max_datetime': fields.Date.to_string(fields.Date.context_today(request.env.user) + timedelta(days=90)) + 'T23:59',
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
        })

        return request.render('mentorize.page_mentors', values)

    # Route mentor_detail: menangani request web untuk fitur ini.
    @http.route('/mentors/<int:mentor_id>', type='http', auth='user', website=True, sitemap=False)
    def mentor_detail(self, mentor_id, **kwargs):
        if self._infer_user_role(request.env.user) == 'alumni':
            return request.redirect('/alumni/dashboard')

        mahasiswa = self._ensure_profile('mahasiswa')
        if not mahasiswa.profile_complete:
            return request.redirect('/profile/setup')

        mentor = request.env['mentorize.alumni'].sudo().browse(mentor_id)
        if not mentor.exists() or not mentor.user_id or not mentor.user_id.active:
            return request.redirect('/mentors?error=Mentor tidak ditemukan')

        score, reasons, label = self._score_mentor(mahasiswa, mentor)
        values = self._layout_values('mentors')
        values.update({
            'mahasiswa': mahasiswa,
            'mentor': mentor,
            'match_score': score,
            'match_reasons': reasons,
            'match_label': label,
            'today_min': fields.Date.to_string(fields.Date.context_today(request.env.user)) + 'T00:00',
            'max_datetime': fields.Date.to_string(fields.Date.context_today(request.env.user) + timedelta(days=90)) + 'T23:59',
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
        })
        return request.render('mentorize.page_mentor_detail', values)

    # Route mentoring_request: menangani request web untuk fitur ini.
    @http.route('/mentoring/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def mentoring_request(self, **kwargs):
        mahasiswa = self._ensure_profile('mahasiswa')
        alumni_id = int(kwargs.get('alumni_id') or 0)
        topik = (kwargs.get('topik') or '').strip()
        deskripsi = kwargs.get('deskripsi') or ''
        date_str = kwargs.get('requested_datetime') or ''

        requested_dt = self._parse_user_datetime(date_str)
        if not requested_dt:
            return request.redirect('/mentors?error=Format tanggal tidak valid')

        today = fields.Date.context_today(request.env.user)
        requested_local = fields.Datetime.context_timestamp(request.env.user, requested_dt)

        if requested_local.date() < today or requested_local.date() > today + timedelta(days=90):
            return request.redirect('/mentors?error=Tanggal mentoring harus antara hari ini sampai 90 hari ke depan')

        alumni = request.env['mentorize.alumni'].sudo().browse(alumni_id)

        if not alumni.exists() or not topik:
            return request.redirect('/mentors?error=Data request belum lengkap')

        if self._schedule_is_past_or_now(requested_dt):
            return request.redirect('/mentors/%s?error=Jadwal mentoring tidak boleh menggunakan waktu yang sudah lewat.' % alumni.id)

        if not alumni.user_id.active or alumni.availability == 'offline':
            return request.redirect('/mentors?error=Mentor sedang tidak tersedia')

        # Kalender mentor baru dikunci jika ada sesi lain yang sudah disetujui/terjadwal/aktif.
        # Pending request belum mengunci kalender karena alumni masih bisa menolak.
        conflict = self._mentor_schedule_conflict(alumni, requested_dt)
        if conflict:
            return request.redirect('/mentors/%s?error=Jadwal tersebut sudah dipakai oleh mentor. Pilih tanggal atau jam lain.' % alumni.id)

        req = request.env['mentorize.request'].sudo().create({
            'mahasiswa_id': mahasiswa.id,
            'alumni_id': alumni.id,
            'topik': topik,
            'deskripsi': deskripsi,
            'requested_datetime': requested_dt,
            'status': 'pending',
        })

        match = request.env['mentorize.matchmaking'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id), ('alumni_id', '=', alumni.id), ('request_id', '=', False)
        ], limit=1)
        if match:
            match.write({'request_id': req.id, 'status': 'requested'})
        else:
            request.env['mentorize.matchmaking'].sudo().create({
                'mahasiswa_id': mahasiswa.id,
                'alumni_id': alumni.id,
                'request_id': req.id,
                'score': 0,
                'alasan': 'Request dibuat langsung oleh mahasiswa.',
                'status': 'requested',
            })

        request.env['mentorize.notification'].sudo().create_notification(
            alumni.user_id,
            'Pengajuan mentoring baru',
            '%s mengajukan mentoring tentang %s.' % (mahasiswa.name, topik),
            notif_type='request_new',
            url='/alumni/dashboard',
        )
        self._log_activity('request', 'Mahasiswa mengajukan request mentoring ke %s: %s' % (alumni.name, topik), 'mentorize.request', req.id, mahasiswa.user_id)

        return request.redirect('/dashboard?success=request')

    @http.route('/mentors/<int:mentor_id>/busy-dates', type='http', auth='user', website=False, methods=['GET'], csrf=False)
    def mentor_busy_dates(self, mentor_id, **kwargs):
        """Endpoint kalender custom: daftar tanggal mentor yang sudah terpakai."""
        mentor = request.env['mentorize.alumni'].sudo().browse(mentor_id)
        if not mentor.exists():
            return self._json({'success': False, 'busy_dates': [], 'busy_ranges': []}, status=404)

        exclude_session = False
        exclude_session_id = int(kwargs.get('exclude_session_id') or 0)
        if exclude_session_id:
            exclude_session = request.env['mentorize.session'].sudo().browse(exclude_session_id)

        busy_dates, busy_ranges = self._busy_dates_for_alumni(mentor, exclude_session=exclude_session if exclude_session and exclude_session.exists() else False)
        return self._json({
            'success': True,
            'mentor_id': mentor.id,
            'busy_dates': busy_dates,
            'busy_ranges': busy_ranges,
        })

    # Route approve_request: menangani request web untuk fitur ini.
    @http.route(['/alumni/request/<int:req_id>/approve', '/mentorize/alumni/request/<int:req_id>/approve'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_request(self, req_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        req = request.env['mentorize.request'].sudo().browse(req_id)
        alumni = self._current_alumni()

        if req.exists() and alumni and req.alumni_id.id == alumni.id:
            if self._schedule_is_past_or_now(req.requested_datetime):
                return request.redirect('/alumni/dashboard?error=Jadwal pengajuan sudah lewat. Tolak pengajuan ini atau minta mahasiswa membuat pengajuan baru.')

            conflict = self._mentor_schedule_conflict(alumni, req.requested_datetime)

            if conflict:
                return request.redirect('/alumni/dashboard?error=Jadwal tersebut sudah terisi. Tolak pengajuan ini atau minta mahasiswa membuat pengajuan baru.')

            req.action_approve()
            return request.redirect('/alumni/dashboard?success=Pengajuan mentoring diterima. Sesi akan aktif otomatis pada jadwal yang disepakati.')

        return request.redirect('/alumni/dashboard')

    # Route reject_request: menangani request web untuk fitur ini.
    @http.route(['/alumni/request/<int:req_id>/reject', '/mentorize/alumni/request/<int:req_id>/reject'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def reject_request(self, req_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        req = request.env['mentorize.request'].sudo().browse(req_id)
        alumni = self._current_alumni()

        if req.exists() and alumni and req.alumni_id.id == alumni.id:
            req.action_reject()
            return request.redirect('/alumni/dashboard?success=Request mentoring ditolak.')

        return request.redirect('/alumni/dashboard')


