from odoo import http, fields
from odoo.http import request
from werkzeug.utils import redirect


class MentorizeSessionController(http.Controller):

    @http.route('/mentorize/session/<int:session_id>/complete', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def action_complete_session(self, session_id, **post):
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists():
            session.action_complete()

        return redirect('/mentorize/alumni/sesi')

    @http.route('/mentorize/session/<int:session_id>/cancel', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def action_cancel_session(self, session_id, **post):
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists():
            cancel_reason = post.get('cancel_reason')

            if cancel_reason:
                session.sudo().write({
                    'cancel_reason': cancel_reason
                })

            session.action_cancel()

        return redirect('/mentorize/alumni/sesi')

    @http.route('/mentorize/session/<int:session_id>/reschedule', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def action_reschedule_session(self, session_id, **post):
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists():
            new_date = post.get('session_date')
            reason = post.get('reschedule_reason')

            values = {}

            if new_date:
                values['session_date'] = new_date

            if reason:
                values['reschedule_reason'] = reason

            if values:
                session.sudo().write(values)

            session.action_reschedule()

        return redirect('/mentorize/alumni/sesi')

    @http.route('/mentorize/chat/<int:room_id>/send', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def send_chat_message(self, room_id, **post):
        room = request.env['mentorize.room.chat'].sudo().browse(room_id)
        isi_pesan = post.get('isi_pesan')

        if room.exists():
            room.send_message(request.env.user.id, isi_pesan)

        if room.session_id:
            return redirect('/mentorize/chat/%s' % room.id)

        return redirect('/mentorize/alumni/sesi')
    
    @http.route('/mentorize/alumni/sesi', type='http', auth='user', website=True)
    def page_sesi_mentoring_alumni(self, **kwargs):
        user = request.env.user

        Session = request.env['mentorize.session'].sudo()

        upcoming_sessions = Session.search([
            ('alumni_id', '=', user.id),
            ('status', 'in', ['scheduled', 'rescheduled']),
        ], order='session_date asc')

        active_sessions = Session.search([
            ('alumni_id', '=', user.id),
            ('status', '=', 'ongoing'),
        ], order='session_date asc')

        history_sessions = Session.search([
            ('alumni_id', '=', user.id),
            ('status', 'in', ['done', 'cancelled']),
        ], order='session_date desc')

        return request.render('mentorize.page_sesi_mentoring_alumni', {
            'upcoming_sessions': upcoming_sessions,
            'active_sessions': active_sessions,
            'history_sessions': history_sessions,
        })