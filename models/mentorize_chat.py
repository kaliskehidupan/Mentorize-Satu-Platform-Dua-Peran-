from odoo import models, fields


class MentorizeRoomChat(models.Model):
    _name = 'mentorize.roomchat'
    _description = 'Room Chat Mentoring'
    _order = 'write_date desc'

    request_id = fields.Many2one('mentorize.request', string='Request', ondelete='cascade')
    session_id = fields.Many2one('mentorize.session', string='Sesi', ondelete='set null')
    mahasiswa_user_id = fields.Many2one('res.users', string='Mahasiswa User')
    alumni_user_id = fields.Many2one('res.users', string='Alumni User')
    status = fields.Selection([
        ('active', 'Aktif'),
        ('closed', 'Ditutup'),
    ], string='Status', default='active')
    message_ids = fields.One2many('mentorize.message', 'room_id', string='Pesan')


class MentorizeMessage(models.Model):
    _name = 'mentorize.message'
    _description = 'Pesan Chat Mentorize'
    _order = 'waktu_kirim asc, id asc'

    room_id = fields.Many2one('mentorize.roomchat', string='Room', required=True, ondelete='cascade', index=True)
    sender_id = fields.Many2one('res.users', string='Pengirim', required=True, ondelete='cascade')
    isi_pesan = fields.Text(string='Isi Pesan', required=True)
    waktu_kirim = fields.Datetime(string='Waktu Kirim', default=fields.Datetime.now, index=True)
