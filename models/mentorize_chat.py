from odoo import models, fields

class MentorizeRoomChat(models.Model):
    _name = 'mentorize.roomchat'
    _description = 'Room Chat Mentoring'

    request_id = fields.Many2one('mentorize.request', string='Request')
    status = fields.Selection([
        ('active', 'Aktif'),
        ('nonaktif', 'Nonaktif'),
    ], string='Status', default='active')
    create_at = fields.Datetime(string='Dibuat', default=fields.Datetime.now)
    message_ids = fields.One2many('mentorize.message', 'room_id', string='Pesan')

class MentorizeMessage(models.Model):
    _name = 'mentorize.message'
    _description = 'Pesan Chat'

    room_id = fields.Many2one('mentorize.roomchat', string='Room', required=True, ondelete='cascade')
    sender_id = fields.Many2one('res.users', string='Pengirim', required=True)
    isi_pesan = fields.Text(string='Isi Pesan', required=True)
    waktu_kirim = fields.Datetime(string='Waktu Kirim', default=fields.Datetime.now)