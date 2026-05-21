from odoo import models, fields

class MentorizeAlumni(models.Model):
    _name = 'mentorize.alumni'
    _description = 'Alumni'

    user_id = fields.Many2one('res.users')

    company = fields.Char(string='Company')
    posisi = fields.Char(string='Posisi')
    bidang = fields.Char(string='Bidang')
    linkedin = fields.Char(string='LinkedIn')

    bio = fields.Text(string='Bio')
    pengalaman = fields.Text(string='Pengalaman')

    slot = fields.Char(string='Slot Mentoring')

    availability = fields.Selection([
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('offline', 'Offline')
    ], default='available')

    is_verified = fields.Boolean(default=False)