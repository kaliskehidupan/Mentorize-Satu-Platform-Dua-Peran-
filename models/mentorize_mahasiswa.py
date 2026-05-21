from odoo import models, fields

class MentorizeMahasiswa(models.Model):
    _name = 'mentorize.mahasiswa'
    _description = 'Profil Mahasiswa'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True
    )

    nim = fields.Char(string='NIM')

    jurusan = fields.Char(string='Jurusan')

    semester = fields.Integer(string='Semester')

    minat_ids = fields.Many2many(
        'mentorize.minat',
        string='Minat'
    )

    skill_ids = fields.Many2many(
        'mentorize.skill',
        string='Skill'
    )