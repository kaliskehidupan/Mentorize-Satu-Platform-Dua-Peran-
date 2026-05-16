from odoo import models, fields

class MentorizeRequest(models.Model):
    _name = 'mentorize.request'
    _description = 'Request Mentoring'

    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True)
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni/Mentor', required=True)
    topik = fields.Char(string='Topik Mentoring', required=True)
    deskripsi = fields.Text(string='Deskripsi/Catatan')
    status = fields.Selection([
        ('pending', 'Menunggu'),
        ('approved', 'Diterima'),
        ('rejected', 'Ditolak'),
    ], string='Status', default='pending')
    tanggal_request = fields.Datetime(string='Tanggal Request', default=fields.Datetime.now)
    session_ids = fields.One2many('mentorize.session', 'request_id', string='Sesi')
    room_chat_id = fields.Many2one('mentorize.roomchat', string='Room Chat')