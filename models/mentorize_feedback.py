from odoo import models, fields

class MentorizeFeedback(models.Model):
    _name = 'mentorize.feedback'
    _description = 'Feedback Mentoring'

    session_id = fields.Many2one('mentorize.session', string='Sesi', required=True)
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni/Mentor', required=True)
    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True)
    rating = fields.Integer(string='Rating', default=5)
    komentar = fields.Text(string='Komentar')
    create_at = fields.Datetime(string='Tanggal', default=fields.Datetime.now)