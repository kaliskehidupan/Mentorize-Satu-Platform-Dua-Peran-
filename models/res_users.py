from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    mentorize_role = fields.Selection([
        ('mahasiswa', 'Mahasiswa'),
        ('alumni', 'Alumni'),
        ('admin', 'Admin Mentorize'),
    ], string='Role Mentorize')

    nim = fields.Char(string='NIM')
    kapa = fields.Char(string='KAPA')
    jurusan = fields.Char(string='Jurusan')

    tujuan_karir = fields.Text(string='Tujuan Karir')

    bio = fields.Text(string='Bio')

    is_verified = fields.Boolean(
        string='Sudah Diverifikasi',
        default=False
    )

    availability = fields.Selection([
        ('available', 'Tersedia'),
        ('busy', 'Sibuk'),
        ('offline', 'Offline'),
    ], string='Ketersediaan', default='available')