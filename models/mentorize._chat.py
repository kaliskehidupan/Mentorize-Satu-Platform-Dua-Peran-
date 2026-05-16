from odoo import models, fields, api
from odoo.exceptions import UserError


class MentorizeRoomChat(models.Model):
    _name = 'mentorize.room.chat'
    _description = 'Room Chat Mentorize'
    _order = 'create_date desc'

    name = fields.Char(string='Nama Room Chat')
    request_id = fields.Many2one(
        'mentorize.request',
        string='Request Mentoring',
        ondelete='cascade'
    )
    mahasiswa_id = fields.Many2one(
        'res.users',
        string='Mahasiswa',
        required=True
    )
    alumni_id = fields.Many2one(
        'res.users',
        string='Alumni',
        required=True
    )
    message_ids = fields.One2many(
        'mentorize.chat.message',
        'room_id',
        string='Pesan'
    )

    def send_message(self, sender_id, isi_pesan):
        """
        Membuat pesan baru pada room chat.
        sender_id = id user yang mengirim pesan.
        isi_pesan = isi chat.
        """
        self.ensure_one()

        if not isi_pesan:
            raise UserError('Isi pesan tidak boleh kosong.')

        sender = self.env['res.users'].browse(int(sender_id))
        if not sender.exists():
            raise UserError('Pengirim tidak ditemukan.')

        if sender not in [self.mahasiswa_id, self.alumni_id]:
            raise UserError('User ini tidak memiliki akses ke room chat.')

        message = self.env['mentorize.chat.message'].sudo().create({
            'room_id': self.id,
            'sender_id': sender.id,
            'isi_pesan': isi_pesan,
        })

        return message

    def get_messages(self):
        """
        Mengambil semua pesan dalam room chat.
        Return berupa list dictionary agar mudah dipakai di controller/template.
        """
        self.ensure_one()

        messages = []
        for msg in self.message_ids.sorted(lambda m: m.create_date):
            messages.append({
                'id': msg.id,
                'sender_id': msg.sender_id.id,
                'sender_name': msg.sender_id.name,
                'isi_pesan': msg.isi_pesan,
                'waktu': msg.create_date,
            })

        return messages


class MentorizeChatMessage(models.Model):
    _name = 'mentorize.chat.message'
    _description = 'Pesan Chat Mentorize'
    _order = 'create_date asc'

    room_id = fields.Many2one(
        'mentorize.room.chat',
        string='Room Chat',
        required=True,
        ondelete='cascade'
    )
    sender_id = fields.Many2one(
        'res.users',
        string='Pengirim',
        required=True
    )
    isi_pesan = fields.Text(
        string='Isi Pesan',
        required=True
    )