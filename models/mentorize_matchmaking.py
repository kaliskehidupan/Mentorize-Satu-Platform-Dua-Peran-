from odoo import models, fields


class MentorizeMatchmaking(models.Model):
    _name = 'mentorize.matchmaking'
    _description = 'Riwayat Matchmaking Mentorize'
    _order = 'create_date desc, score desc'

    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True, ondelete='cascade')
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni / Mentor', required=True, ondelete='cascade')
    request_id = fields.Many2one('mentorize.request', string='Request Mentoring', ondelete='set null')
    score = fields.Float(string='Skor Kecocokan', default=0.0)
    alasan = fields.Text(string='Alasan Rekomendasi')
    status = fields.Selection([
        ('recommended', 'Direkomendasikan'),
        ('requested', 'Diajukan'),
        ('approved', 'Diterima'),
        ('rejected', 'Ditolak'),
    ], default='recommended')
