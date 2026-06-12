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


class MentorizeSessionController(MentorizeBaseController):
    # Semua method di class ini adalah route Odoo untuk fitur yang sesuai nama file.
    # ---------- ending session, summary, history ----------
    # Route finish_session_form: menangani request web untuk fitur ini.
    @http.route('/session/<int:session_id>/finish', type='http', auth='user', website=True, sitemap=False)
    def finish_session_form(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists() or not mahasiswa or session.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/dashboard')
        if session.status in ['completed', 'stopped', 'cancelled']:
            return request.redirect('/history/%s' % session.id)
        values = self._layout_values('history')
        values.update({'session': session, 'error': kwargs.get('error')})
        return request.render('mentorize.page_session_finish', values)

    # Route request_end_session: menangani request web untuk fitur ini.
    @http.route('/session/<int:session_id>/end/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def request_end_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and mahasiswa and session.mahasiswa_id.id == mahasiswa.id:
            rating = int(kwargs.get('completion_rating') or kwargs.get('rating') or 5)
            rating = max(1, min(rating, 5))
            session.write({
                'status': 'end_requested',
                'end_request_note': kwargs.get('completion_summary') or kwargs.get('note') or '',
                'end_requested_at': fields.Datetime.now(),
                'completion_requested_by': request.env.user.id,
                'completion_title': kwargs.get('completion_title') or session.topik,
                'completion_method': kwargs.get('completion_method') or session.mode,
                'completion_summary': kwargs.get('completion_summary') or '',
                'material_discussed': kwargs.get('material_discussed') or '',
                'mentoring_result': kwargs.get('mentoring_result') or '',
                'follow_up_note': kwargs.get('follow_up_note') or '',
                'student_obstacle': kwargs.get('student_obstacle') or '',
                'completion_feedback': kwargs.get('completion_feedback') or '',
                'completion_rating': rating,
                'summary_topic': kwargs.get('completion_title') or session.topik,
                'summary_learnings': kwargs.get('mentoring_result') or kwargs.get('completion_summary') or '',
                'summary_advice': kwargs.get('follow_up_note') or '',
                'summary_next_steps': kwargs.get('follow_up_note') or '',
                'summary_notes': kwargs.get('student_obstacle') or '',
            })

            request.env['mentorize.notification'].sudo().create_notification(
                session.alumni_id.user_id,
                'Pengajuan akhir sesi',
                '%s mengajukan sesi mentoring untuk diselesaikan dan mengirim laporan hasil mentoring.' % mahasiswa.name,
                notif_type='session_end_requested',
                url='/alumni/dashboard',
            )
            self._log_activity('session', 'Mahasiswa mengajukan selesai mentoring: %s' % (session.topik or ''), 'mentorize.session', session.id, mahasiswa.user_id)

        return request.redirect('/dashboard')

    # Route approve_end_session: menangani request web untuk fitur ini.
    @http.route('/session/<int:session_id>/end/approve', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_end_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        alumni = self._current_alumni()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and alumni and session.alumni_id.id == alumni.id:
            session.write({
                'status': 'completed',
                'completed_at': fields.Datetime.now(),
                'completion_approved_by': request.env.user.id,
                'summary_saved': True,
            })

            session.request_id.write({'status': 'done'})

            if session.request_id.room_chat_id:
                session.request_id.room_chat_id.write({
                    'status': 'closed',
                    'closed_reason': 'Sesi mentoring selesai',
                    'closed_at': fields.Datetime.now(),
                })

            if not session.feedback_id:
                feedback = request.env['mentorize.feedback'].sudo().create({
                    'session_id': session.id,
                    'alumni_id': session.alumni_id.id,
                    'mahasiswa_id': session.mahasiswa_id.id,
                    'rating': session.completion_rating or 5,
                    'komentar': session.completion_feedback or session.completion_summary or '',
                })
                session.feedback_id = feedback.id

            request.env['mentorize.laporan'].sudo().create({
                'session_id': session.id,
                'mahasiswa_id': session.mahasiswa_id.id,
                'alumni_id': session.alumni_id.id,
                'judul': session.completion_title or session.topik or 'Laporan mentoring',
                'ringkasan': session.completion_summary or session.mentoring_result or '',
                'status': 'pending',
            })

            request.env['mentorize.notification'].sudo().create_notification(
                session.mahasiswa_id.user_id,
                'Sesi mentoring selesai',
                'Sesi mentoring kamu telah disetujui selesai. Laporan sudah masuk ke riwayat.',
                notif_type='session_completed',
                url='/history/%s' % session.id,
            )

            email_body = (
                'Halo,\n\n'
                'Sesi mentoring Mentorize telah selesai. Berikut laporan singkatnya:\n\n'
                'Judul mentoring: %s\n'
                'Mahasiswa: %s\n'
                'Mentor/Alumni: %s\n'
                'Waktu mentoring: %s\n'
                'Metode: %s\n\n'
                'Ringkasan pembahasan:\n%s\n\n'
                'Materi yang dibahas:\n%s\n\n'
                'Hal yang didapatkan / insight:\n%s\n\n'
                'Tindak lanjut:\n%s\n\n'
                'Kendala selama mentoring:\n%s\n\n'
                'Catatan/feedback:\n%s\n\n'
                'Laporan ini otomatis dikirim oleh Mentorize setelah mentor menyetujui penyelesaian sesi.'
            ) % (
                session.completion_title or session.topik or 'Mentoring',
                session.mahasiswa_id.name or '-',
                session.alumni_id.name or '-',
                self._format_user_datetime(session.tanggal_mentoring) if session.tanggal_mentoring else '-',
                dict(session._fields['completion_method'].selection).get(session.completion_method, session.completion_method or session.mode or '-'),
                session.completion_summary or '-',
                session.material_discussed or '-',
                session.mentoring_result or session.summary_learnings or '-',
                session.follow_up_note or session.summary_next_steps or '-',
                session.student_obstacle or '-',
                session.completion_feedback or session.summary_notes or '-',
            )
            for target in [session.mahasiswa_id.user_id, session.alumni_id.user_id]:
                self._send_mentorize_email(
                    target,
                    self._email_subject('Laporan Selesai Mentoring'),
                    email_body,
                )

            self._log_activity('session', 'Alumni menyetujui selesai mentoring: %s' % (session.topik or ''), 'mentorize.session', session.id, alumni.user_id)

        return request.redirect('/alumni/dashboard')

    # Route reject_end_session: menangani request web untuk fitur ini.
    @http.route('/session/<int:session_id>/end/reject', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def reject_end_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        alumni = self._current_alumni()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and alumni and session.alumni_id.id == alumni.id:
            session.write({'status': 'active' if not session.expired_at or fields.Datetime.now() <= session.expired_at else 'time_expired'})

            request.env['mentorize.notification'].sudo().create_notification(
                session.mahasiswa_id.user_id,
                'Pengajuan akhir sesi belum disetujui',
                'Mentor merasa sesi masih perlu dilanjutkan.',
                notif_type='info',
                url='/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''),
            )

        return request.redirect('/alumni/dashboard')

    # ---------- Tambah Waktu Sesi ----------
    @http.route('/session/<int:session_id>/extension/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def request_extension_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        """Mahasiswa/alumni mengajukan tambahan waktu setelah sesi melewati batas 2 x 24 jam."""
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/chat')

        user = request.env.user
        allowed = user.id in [session.mahasiswa_id.user_id.id, session.alumni_id.user_id.id]
        if not allowed or session.status not in ['time_expired', 'extension_pending']:
            return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

        date_str = kwargs.get('extension_datetime') or ''
        new_dt = self._parse_user_datetime(date_str)
        if not new_dt:
            return request.redirect('/chat?room_id=%s&error=Format tanggal tambahan tidak valid' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

        if self._schedule_is_past_or_now(new_dt):
            return request.redirect('/chat?room_id=%s&error=Jadwal tambahan tidak boleh menggunakan waktu yang sudah lewat' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

        conflict = self._mentor_schedule_conflict(session.alumni_id, new_dt, exclude_session=session)
        if conflict:
            return request.redirect('/chat?room_id=%s&error=Jadwal tambahan tersebut sudah dipakai mentor. Pilih jadwal lain.' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

        session.write({
            'status': 'extension_pending',
            'extension_requested_datetime': new_dt,
            'extension_note': kwargs.get('extension_note') or '',
            'extension_requested_by': user.id,
            'extension_requested_at': fields.Datetime.now(),
        })

        target = session.alumni_id.user_id if user.id == session.mahasiswa_id.user_id.id else session.mahasiswa_id.user_id
        request.env['mentorize.notification'].sudo().create_notification(
            target,
            'Pengajuan tambah waktu',
            '%s mengajukan tambahan waktu untuk sesi "%s".' % (user.name, session.topik or 'Mentoring'),
            'session_extension_requested',
            '/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''),
        )
        self._log_activity('session', 'Mengajukan tambah waktu sesi: %s' % (session.topik or ''), 'mentorize.session', session.id)
        return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

    @http.route('/session/<int:session_id>/extension/approve', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_extension_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        """Alumni menyetujui tambahan waktu. Sesi kembali terjadwal/aktif sesuai tanggal tambahan."""
        session = request.env['mentorize.session'].sudo().browse(session_id)
        alumni = self._current_alumni()
        if session.exists() and alumni and session.alumni_id.id == alumni.id and session.status == 'extension_pending':
            new_dt = session.extension_requested_datetime
            if self._schedule_is_past_or_now(new_dt):
                return request.redirect('/alumni/dashboard?error=Jadwal tambahan sudah lewat. Minta user mengajukan jadwal baru.')

            conflict = self._mentor_schedule_conflict(session.alumni_id, new_dt, exclude_session=session)
            if conflict:
                return request.redirect('/alumni/dashboard?error=Jadwal tambahan tersebut sudah dipakai mentor.')

            session.write({
                'tanggal_mentoring': new_dt,
                'status': 'scheduled',
                'started_at': False,
                'expired_at': False,
                'session_end_at': new_dt + timedelta(hours=session.duration_hours or 48),
                'extension_approved_by': request.env.user.id,
                'extension_approved_at': fields.Datetime.now(),
            })
            for target in [session.mahasiswa_id.user_id, session.alumni_id.user_id]:
                request.env['mentorize.notification'].sudo().create_notification(
                    target,
                    'Tambah waktu disetujui',
                    'Tambahan waktu sesi "%s" disetujui. Sesi aktif otomatis pada jadwal baru.' % (session.topik or 'Mentoring'),
                    'session_extension_approved',
                    '/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''),
                )
            self._log_activity('session', 'Menyetujui tambah waktu sesi: %s' % (session.topik or ''), 'mentorize.session', session.id, alumni.user_id)
        return request.redirect('/alumni/dashboard')

    @http.route('/session/<int:session_id>/extension/reject', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def reject_extension_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        """Alumni menolak tambahan waktu. Sesi kembali ke status waktu habis agar mahasiswa bisa ajukan selesai atau jadwal lain."""
        session = request.env['mentorize.session'].sudo().browse(session_id)
        alumni = self._current_alumni()
        if session.exists() and alumni and session.alumni_id.id == alumni.id and session.status == 'extension_pending':
            session.write({
                'status': 'time_expired',
                'extension_rejected_at': fields.Datetime.now(),
            })
            request.env['mentorize.notification'].sudo().create_notification(
                session.mahasiswa_id.user_id,
                'Tambah waktu ditolak',
                'Mentor menolak pengajuan tambahan waktu. Kamu bisa memilih jadwal lain atau ajukan penyelesaian sesi.',
                'session_extension_rejected',
                '/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''),
            )
            self._log_activity('session', 'Menolak tambah waktu sesi: %s' % (session.topik or ''), 'mentorize.session', session.id, alumni.user_id)
        return request.redirect('/alumni/dashboard')

    # Route request_stop_session: menangani request web untuk fitur ini.
    @http.route('/session/<int:session_id>/stop/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def request_stop_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/chat')
        user = request.env.user
        allowed = user.id in [session.mahasiswa_id.user_id.id, session.alumni_id.user_id.id]
        if allowed and session.status not in ['completed', 'stopped', 'cancelled']:
            reason = kwargs.get('stop_reason') or 'Pengajuan berhenti mentoring.'
            session.write({
                'status': 'stop_requested',
                'stop_requested_by': user.id,
                'stop_reason': reason,
                'stop_requested_at': fields.Datetime.now(),
            })
            target = session.alumni_id.user_id if user.id == session.mahasiswa_id.user_id.id else session.mahasiswa_id.user_id
            request.env['mentorize.notification'].sudo().create_notification(target, 'Pengajuan berhenti mentoring', '%s mengajukan penghentian mentoring.' % user.name, 'session_stop_requested', '/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
            self._log_activity('session', 'Pengajuan berhenti mentoring: %s' % reason, 'mentorize.session', session.id)
        return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

    # Route approve_stop_session: menangani request web untuk fitur ini.
    @http.route('/session/<int:session_id>/stop/approve', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_stop_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/chat')
        user = request.env.user
        allowed = self._is_admin() or user.id in [session.mahasiswa_id.user_id.id, session.alumni_id.user_id.id]
        if allowed and session.status == 'stop_requested':
            session.write({
                'status': 'stopped',
                'stopped_at': fields.Datetime.now(),
                'stop_approved_by': user.id,
            })
            session.request_id.write({'status': 'done'})
            if session.request_id.room_chat_id:
                session.request_id.room_chat_id.write({
                    'status': 'closed',
                    'closed_reason': 'Mentoring dihentikan',
                    'closed_at': fields.Datetime.now(),
                })
            for target in [session.mahasiswa_id.user_id, session.alumni_id.user_id]:
                request.env['mentorize.notification'].sudo().create_notification(target, 'Mentoring dihentikan', 'Mentoring "%s" sudah dihentikan dan chat dikunci.' % (session.topik or ''), 'session_stopped', '/history/%s' % session.id)
            self._log_activity('session', 'Mentoring dihentikan: %s' % (session.stop_reason or ''), 'mentorize.session', session.id)
        return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

    # Route reschedule_session: menangani request web untuk fitur ini.
    @http.route('/session/<int:session_id>/reschedule', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def reschedule_session(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/chat')
        user = request.env.user
        allowed = user.id in [session.mahasiswa_id.user_id.id, session.alumni_id.user_id.id]
        date_str = kwargs.get('tanggal_mentoring') or ''
        new_dt = self._parse_user_datetime(date_str)
        if not new_dt:
            return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
        if self._schedule_is_past_or_now(new_dt):
            return request.redirect('/chat?room_id=%s&error=Jadwal baru tidak boleh menggunakan waktu yang sudah lewat.' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
        if allowed and session.status not in ['completed', 'stopped', 'cancelled']:
            conflict = self._mentor_schedule_conflict(session.alumni_id, new_dt, exclude_session=session)
            if conflict:
                return request.redirect('/chat?room_id=%s&error=Jadwal tersebut sudah dipakai mentor. Pilih jadwal lain.' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
            session.write({
                'tanggal_mentoring': new_dt,
                'status': 'scheduled',
                'started_at': False,
                'expired_at': False,
                'session_end_at': new_dt + timedelta(hours=session.duration_hours or 48),
                'reschedule_reason': kwargs.get('reschedule_reason') or '',
                'reschedule_requested_at': fields.Datetime.now(),
            })
            target = session.alumni_id.user_id if user.id == session.mahasiswa_id.user_id.id else session.mahasiswa_id.user_id
            request.env['mentorize.notification'].sudo().create_notification(target, 'Jadwal mentoring diubah', 'Jadwal mentoring "%s" diperbarui.' % (session.topik or ''), 'reschedule', '/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
            self._log_activity('session', 'Reschedule mentoring: %s' % (session.topik or ''), 'mentorize.session', session.id)
        return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

    # Route summary: menangani request web untuk fitur ini.
    @http.route('/summary/<int:session_id>', type='http', auth='user', website=True, sitemap=False)
    def summary(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if not session.exists() or not mahasiswa or session.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/dashboard')

        values = self._layout_values('history')
        values.update({'session': session, 'success': kwargs.get('success')})
        return request.render('mentorize.page_summary', values)

    # Route summary_save: menangani request web untuk fitur ini.
    @http.route('/summary/<int:session_id>/save', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def summary_save(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and mahasiswa and session.mahasiswa_id.id == mahasiswa.id:
            session.write({
                'summary_saved': True,
                'summary_topic': kwargs.get('summary_topic') or session.summary_topic or session.topik,
                'summary_learnings': kwargs.get('summary_learnings') or session.summary_learnings or '',
                'summary_advice': kwargs.get('summary_advice') or session.summary_advice or '',
                'summary_next_steps': kwargs.get('summary_next_steps') or session.summary_next_steps or '',
                'summary_notes': kwargs.get('summary_notes') or session.summary_notes or '',
            })
            rating = int(kwargs.get('rating') or session.completion_rating or 5)
            komentar = kwargs.get('komentar') or session.completion_feedback or ''
            if session.feedback_id:
                session.feedback_id.write({'rating': rating, 'komentar': komentar})
            else:
                feedback = request.env['mentorize.feedback'].sudo().create({
                    'session_id': session.id,
                    'alumni_id': session.alumni_id.id,
                    'mahasiswa_id': session.mahasiswa_id.id,
                    'rating': rating,
                    'komentar': komentar,
                })
                session.feedback_id = feedback.id
        return request.redirect('/history')

    # Route history: menangani request web untuk fitur ini.
    @http.route('/history', type='http', auth='user', website=True, sitemap=False)
    def history(self, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        role = self._infer_user_role(request.env.user)
        domain = [('status', 'in', ['completed', 'stopped', 'cancelled'])]
        if role == 'alumni':
            alumni = self._current_alumni()
            if not alumni:
                return request.redirect('/alumni/dashboard')
            domain.append(('alumni_id', '=', alumni.id))
        else:
            mahasiswa = self._current_mahasiswa()
            if not mahasiswa:
                return request.redirect('/dashboard')
            domain.append(('mahasiswa_id', '=', mahasiswa.id))
        sessions = request.env['mentorize.session'].sudo().search(domain, order='completed_at desc, stopped_at desc, tanggal_mentoring desc')
        values = self._layout_values('history')
        values.update({'sessions': sessions, 'history_role': role})
        return request.render('mentorize.page_history', values)

    # Route history_detail: menangani request web untuk fitur ini.
    @http.route('/history/<int:session_id>', type='http', auth='user', website=True, sitemap=False)
    def history_detail(self, session_id, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        role = self._infer_user_role(request.env.user)
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/history')
        allowed = self._is_admin() or (session.mahasiswa_id.user_id.id == request.env.user.id) or (session.alumni_id.user_id.id == request.env.user.id)
        if not allowed:
            return request.redirect('/history')
        values = self._layout_values('history')
        values.update({'session': session, 'history_role': role})
        return request.render('mentorize.page_history_detail', values)


