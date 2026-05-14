from odoo import models, fields, api


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
        'mentorize.message',
        'room_id',
        string='Pesan'
    )
    status = fields.Selection([
        ('active', 'Aktif'),
        ('closed', 'Selesai'),
    ], string='Status', default='active')

    last_message = fields.Char(
        string='Pesan Terakhir',
        compute='_compute_last_message'
    )

    @api.depends('message_ids', 'message_ids.isi_pesan')
    def _compute_last_message(self):
        for room in self:
            last_msg = room.message_ids[-1] if room.message_ids else False
            room.last_message = last_msg.isi_pesan if last_msg else 'Mulai percakapan...'


class MentorizeMessage(models.Model):
    _name = 'mentorize.message'
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
        required=True,
        default=lambda self: self.env.user
    )
    receiver_id = fields.Many2one(
        'res.users',
        string='Penerima'
    )
    isi_pesan = fields.Text(
        string='Isi Pesan',
        required=True
    )
    is_read = fields.Boolean(
        string='Sudah Dibaca',
        default=False
    )