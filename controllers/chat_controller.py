from odoo import http
from odoo.http import request


class MentorizeChatController(http.Controller):

    @http.route('/mentorize/mahasiswa/chat', type='http', auth='user', website=True)
    def mahasiswa_chat_page(self, **kwargs):
        return request.render('mentorize.chat_page')

    @http.route('/mentorize/alumni/chat', type='http', auth='user', website=True)
    def alumni_chat_page(self, **kwargs):
        return request.render('mentorize.chat_page')

    @http.route('/mentorize/chat/data', type='json', auth='user')
    def get_chat_data(self, room_id=None, **kwargs):
        user = request.env.user

        rooms = request.env['mentorize.room.chat'].sudo().search([
            '|',
            ('mahasiswa_id', '=', user.id),
            ('alumni_id', '=', user.id)
        ])

        room_data = []

        for room in rooms:
            partner = room.alumni_id if room.mahasiswa_id.id == user.id else room.mahasiswa_id
            last_message = room.message_ids[-1] if room.message_ids else False

            room_data.append({
                'id': room.id,
                'name': partner.name if partner else 'Pengguna',
                'avatar': partner.name[:1].upper() if partner and partner.name else 'U',
                'last_message': last_message.isi_pesan if last_message else 'Mulai percakapan...',
                'time': last_message.create_date.strftime('%H:%M') if last_message else '',
                'status': room.status,
            })

        selected_room = False

        if room_id:
            selected_room = rooms.filtered(lambda r: r.id == int(room_id))[:1]

        if not selected_room and rooms:
            selected_room = rooms[:1]

        messages = []
        detail = {}

        if selected_room:
            partner = selected_room.alumni_id if selected_room.mahasiswa_id.id == user.id else selected_room.mahasiswa_id

            for msg in selected_room.message_ids:
                messages.append({
                    'id': msg.id,
                    'text': msg.isi_pesan,
                    'time': msg.create_date.strftime('%H:%M'),
                    'is_me': msg.sender_id.id == user.id,
                    'sender_name': msg.sender_id.name,
                    'avatar': msg.sender_id.name[:1].upper() if msg.sender_id.name else 'U',
                })

            detail = {
                'name': partner.name if partner else 'Pengguna',
                'title': 'Mentor' if selected_room.alumni_id.id == partner.id else 'Mahasiswa',
                'status': 'Aktif',
                'progress': 65,
                'session_text': 'Room chat konsultasi awal',
                'avatar': partner.name[:1].upper() if partner and partner.name else 'U',
            }

        return {
            'current_user': {
                'id': user.id,
                'name': user.name,
                'role': 'Mahasiswa / Alumni',
                'avatar': user.name[:1].upper() if user.name else 'U',
            },
            'selected_room_id': selected_room.id if selected_room else False,
            'conversations': room_data,
            'messages': messages,
            'mentor_detail': detail,
        }

    @http.route('/mentorize/chat/send', type='json', auth='user')
    def send_message(self, room_id=None, message=None, **kwargs):
        user = request.env.user

        if not room_id or not message:
            return {
                'success': False,
                'error': 'Room chat atau pesan kosong.'
            }

        room = request.env['mentorize.room.chat'].sudo().browse(int(room_id))

        if not room.exists():
            return {
                'success': False,
                'error': 'Room chat tidak ditemukan.'
            }

        if user.id not in [room.mahasiswa_id.id, room.alumni_id.id]:
            return {
                'success': False,
                'error': 'Anda tidak memiliki akses ke room chat ini.'
            }

        receiver = room.alumni_id if room.mahasiswa_id.id == user.id else room.mahasiswa_id

        new_message = request.env['mentorize.message'].sudo().create({
            'room_id': room.id,
            'sender_id': user.id,
            'receiver_id': receiver.id,
            'isi_pesan': message,
        })

        return {
            'success': True,
            'message': {
                'id': new_message.id,
                'text': new_message.isi_pesan,
                'time': new_message.create_date.strftime('%H:%M'),
                'is_me': True,
                'sender_name': user.name,
                'avatar': user.name[:1].upper() if user.name else 'U',
            }
        }