from odoo import models, fields


class MentorizeFeedback(models.Model):
    _name = 'mentorize.feedback'
    _description = 'Feedback Mentoring'
    _order = 'create_date desc'

    session_id = fields.Many2one('mentorize.session', string='Sesi', required=True, ondelete='cascade')
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni / Mentor', required=True, ondelete='cascade')
    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True, ondelete='cascade')
    rating = fields.Integer(string='Rating', default=5)
    komentar = fields.Text(string='Komentar')
