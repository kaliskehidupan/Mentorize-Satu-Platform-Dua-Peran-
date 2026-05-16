from odoo import http
from odoo.http import request
from datetime import datetime


class MentorizeSesiMentoringController(http.Controller):

    def _get_current_mahasiswa(self):
        return request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)

    @http.route('/mentorize/mahasiswa/sesi', type='http', auth='user', website=True)
    def sesi_mentoring_mahasiswa(self, **kwargs):
        mahasiswa = self._get_current_mahasiswa()

        all_sessions = request.env['mentorize.session'].sudo().search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id)
        ], order='tanggal_mentoring desc')

        upcoming_sessions = all_sessions.filtered(
            lambda s: s.status in ['scheduled', 'rescheduled']
        )

        running_sessions = all_sessions.filtered(
            lambda s: s.status == 'scheduled'
        )

        history_sessions = all_sessions.filtered(
            lambda s: s.status in ['completed', 'cancelled']
        )

        approved_requests = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'approved')
        ], order='tanggal_request desc')

        return request.render('mentorize.sesi_mentoring_mahasiswa_template', {
            'mahasiswa': mahasiswa,
            'upcoming_sessions': upcoming_sessions,
            'running_sessions': running_sessions,
            'history_sessions': history_sessions,
            'approved_requests': approved_requests,
        })

    @http.route('/mentorize/mahasiswa/sesi/ajukan', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def ajukan_sesi_mahasiswa(self, **post):
        request_id = post.get('request_id')
        tanggal_mentoring = post.get('tanggal_mentoring')
        durasi = post.get('durasi') or 60
        mode = post.get('mode') or 'offline'
        lokasi_link = post.get('lokasi_link') or ''
        ringkasan_materi = post.get('ringkasan_materi') or ''

        if not request_id:
            return request.redirect('/mentorize/mahasiswa/sesi')

        if not tanggal_mentoring:
            return request.redirect('/mentorize/mahasiswa/sesi')

        # Format dari HTML datetime-local: 2026-05-17T04:06
        # Diubah menjadi Python datetime supaya aman untuk fields.Datetime Odoo
        tanggal_mentoring = datetime.strptime(
        tanggal_mentoring,
        '%Y-%m-%dT%H:%M'
        )


        request.env['mentorize.session'].sudo().create({
            'request_id': int(request_id),
            'tanggal_mentoring': tanggal_mentoring,
            'durasi': int(durasi),
            'mode': mode,
            'lokasi_link': lokasi_link,
            'ringkasan_materi': ringkasan_materi,
            'status': 'scheduled',
        })

        return request.redirect('/mentorize/mahasiswa/sesi')

    @http.route('/mentorize/session/<int:session_id>/complete', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def complete_session(self, session_id, **post):
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists():
            session.action_complete()

        return request.redirect(request.httprequest.referrer or '/mentorize/mahasiswa/sesi')

    @http.route('/mentorize/session/<int:session_id>/cancel', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def cancel_session(self, session_id, **post):
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists():
            cancel_reason = post.get('cancel_reason')
            vals = {
                'status': 'cancelled'
            }

            if cancel_reason:
                vals['ringkasan_materi'] = cancel_reason

            session.write(vals)

        return request.redirect(request.httprequest.referrer or '/mentorize/mahasiswa/sesi')

    @http.route('/mentorize/session/<int:session_id>/reschedule', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def reschedule_session(self, session_id, **post):
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists():
            tanggal_mentoring = post.get('tanggal_mentoring')
            ringkasan_materi = post.get('ringkasan_materi') or ''

            vals = {
                'status': 'rescheduled'
            }

            if tanggal_mentoring:
                vals['tanggal_mentoring'] = datetime.strptime(
                    tanggal_mentoring,
                    '%Y-%m-%dT%H:%M'
                )

            if ringkasan_materi:
                vals['ringkasan_materi'] = ringkasan_materi

            session.write(vals)

        return request.redirect(request.httprequest.referrer or '/mentorize/mahasiswa/sesi')