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


class MentorizeDashboardController(MentorizeBaseController):
    # Semua method di class ini adalah route Odoo untuk fitur yang sesuai nama file.
    # ---------- dashboard ----------
    # Route dashboard: menangani request web untuk fitur ini.
    @http.route('/dashboard', type='http', auth='user', website=True, sitemap=False)
    def dashboard(self, **kwargs):
        role = self._sync_user_role(request.env.user)

        if role == 'alumni':
            return request.redirect('/alumni/dashboard')
        if role == 'admin':
            return request.redirect('/admin/dashboard')

        return self.dashboard_mahasiswa(**kwargs)

    # Route old_dashboard_mahasiswa: menangani request web untuk fitur ini.
    @http.route(['/mentorize/mahasiswa/dashboard'], type='http', auth='user', website=True, sitemap=False)
    def old_dashboard_mahasiswa(self, **kwargs):
        return request.redirect('/dashboard')

    # Route dashboard_mahasiswa_alias: menangani request web untuk fitur ini.
    @http.route('/dashboard/mahasiswa', type='http', auth='user', website=True, sitemap=False)
    def dashboard_mahasiswa_alias(self, **kwargs):
        return self.dashboard_mahasiswa(**kwargs)

    def dashboard_mahasiswa(self, **kwargs):
        if self._infer_user_role(request.env.user) == 'alumni':
            return request.redirect('/alumni/dashboard')

        mahasiswa = self._ensure_profile('mahasiswa')

        if not mahasiswa.profile_complete:
            return request.redirect('/profile/setup')

        Request = request.env['mentorize.request'].sudo()
        Session = request.env['mentorize.session'].sudo()

        # Fallback cron: pastikan sesi yang jadwalnya sudah tiba berubah aktif saat beranda dibuka.
        self._sync_session_lifecycle(Session.search([('mahasiswa_id', '=', mahasiswa.id)]))

        pending_requests = Request.search([('mahasiswa_id', '=', mahasiswa.id), ('status', '=', 'pending')], limit=5)
        active_requests = Request.search([('mahasiswa_id', '=', mahasiswa.id), ('status', '=', 'approved')], limit=5)

        upcoming_sessions = Session.search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', 'in', ['scheduled', 'active', 'time_expired', 'extension_pending', 'end_requested'])
        ], order='tanggal_mentoring asc', limit=6)

        completed_sessions = Session.search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'completed')
        ], order='completed_at desc, tanggal_mentoring desc', limit=5)

        recommended = self._recommend_mentors(mahasiswa, limit=3)
        ranked_recommended = self._rank_mentors(mahasiswa, recommended)
        match_context = self._mentor_match_context(ranked_recommended)

        values = self._layout_values('dashboard')
        values.update({
            'mahasiswa': mahasiswa,
            'recommended_mentors': recommended,
            'match_scores': match_context['match_scores'],
            'match_reasons': match_context['match_reasons'],
            'match_labels': match_context['match_labels'],
            'pending_requests': pending_requests,
            'active_requests': active_requests,
            'upcoming_sessions': upcoming_sessions,
            'completed_sessions': completed_sessions,
            'stats': {
                'mentor_rekomendasi': len(recommended),
                'request_pending': len(pending_requests),
                'sesi_aktif': len(upcoming_sessions),
                'sesi_selesai': len(completed_sessions),
            },
            'today': fields.Date.context_today(request.env.user),
            'max_date': fields.Date.context_today(request.env.user) + timedelta(days=90),
            'today_min': fields.Date.to_string(fields.Date.context_today(request.env.user)) + 'T00:00',
            'max_datetime': fields.Date.to_string(fields.Date.context_today(request.env.user) + timedelta(days=90)) + 'T23:59',
        })

        return request.render('mentorize.dashboard_mahasiswa', values)

    # Route dashboard_alumni: menangani request web untuk fitur ini.
    @http.route(['/alumni/dashboard', '/mentorize/alumni/dashboard'], type='http', auth='user', website=True, sitemap=False)
    def dashboard_alumni(self, **kwargs):
        if self._infer_user_role(request.env.user) != 'alumni':
            return request.redirect('/dashboard')

        alumni = self._ensure_profile('alumni')

        if not alumni.profile_complete:
            return request.redirect('/alumni/profile/setup')

        Request = request.env['mentorize.request'].sudo()
        Session = request.env['mentorize.session'].sudo()

        # Fallback cron: pastikan sesi alumni otomatis aktif saat jadwal sudah tiba.
        self._sync_session_lifecycle(Session.search([('alumni_id', '=', alumni.id)]))

        requests_list = Request.search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'pending')
        ], order='tanggal_request desc')

        upcoming_sessions = Session.search([
            ('alumni_id', '=', alumni.id),
            ('status', 'in', ['scheduled', 'active', 'time_expired', 'extension_pending', 'end_requested'])
        ], order='tanggal_mentoring asc')

        completed_sessions = Session.search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'completed')
        ], order='completed_at desc, tanggal_mentoring desc', limit=5)

        end_requests = Session.search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'end_requested')
        ], order='end_requested_at desc')

        req_ranked = []
        for req in requests_list:
            score, reasons, label = self._score_mentor(req.mahasiswa_id, alumni)
            req_ranked.append({'request': req, 'score': score, 'reasons': reasons, 'label': label})
        req_match_scores = {item['request'].id: item['score'] for item in req_ranked}
        req_match_labels = {item['request'].id: item['label'] for item in req_ranked}
        req_match_reasons = {item['request'].id: item['reasons'] for item in req_ranked}

        values = self._layout_values('dashboard')
        values.update({
            'alumni': alumni,
            'request_match_scores': req_match_scores,
            'request_match_labels': req_match_labels,
            'request_match_reasons': req_match_reasons,
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
            'requests': requests_list,
            'upcoming_sessions': upcoming_sessions,
            'completed_sessions': completed_sessions,
            'end_requests': end_requests,
            'stats': {
                'permintaan_baru': len(requests_list),
                'sesi_aktif': len(upcoming_sessions),
                'sesi_selesai': len(completed_sessions),
                'rating': alumni.rating,
            },
        })

        return request.render('mentorize.dashboard_alumni', values)


