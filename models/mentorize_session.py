from odoo import models, fields

class MentorizeSession(models.Model):
    _name = 'mentorize.session'
    _description = 'Sesi Mentoring'

    request_id = fields.Many2one('mentorize.request', string='Request', required=True)
    tanggal_mentoring = fields.Datetime(string='Tanggal & Jam Sesi', required=True)
    durasi = fields.Integer(string='Durasi (menit)', default=60)
    mode = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Mode', default='offline')
    lokasi_link = fields.Char(string='Lokasi / Link Meeting')
    ringkasan_materi = fields.Text(string='Ringkasan Materi')
    status = fields.Selection([
        ('scheduled', 'Terjadwal'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan'),
        ('rescheduled', 'Dijadwalkan Ulang'),
    ], string='Status', default='scheduled')
    feedback_id = fields.Many2one('mentorize.feedback', string='Feedback')