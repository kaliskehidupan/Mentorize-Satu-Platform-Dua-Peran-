from odoo import models, fields

class MentorizeMatchmaking(models.Model):
    _name = 'mentorize.matchmaking'
    _description = 'Matchmaking Mentor-Mentee'

    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True)
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni/Mentor', required=True)
    skor_kecocokan = fields.Float(string='Skor Kecocokan')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('matched', 'Matched'),
        ('rejected', 'Rejected'),
    ], string='State', default='pending')
    create_at = fields.Datetime(string='Tanggal', default=fields.Datetime.now)