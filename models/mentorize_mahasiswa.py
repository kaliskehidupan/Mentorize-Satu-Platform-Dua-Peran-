from odoo import models, fields

class MentorizeMahasiswa(models.Model):
    _name = 'mentorize.mahasiswa'
    _description = 'Profil Mahasiswa'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    name = fields.Char(related='user_id.name', string='Nama', readonly=True)
    nim = fields.Char(string='NIM', required=True)
    jurusan = fields.Char(string='Jurusan')
    semester = fields.Integer(string='Semester')
    tujuan_karir = fields.Text(string='Tujuan Karir')
    minat_ids = fields.Many2many('mentorize.minat', string='Minat')
    skill_ids = fields.Many2many('mentorize.skill', string='Skill')
    request_ids = fields.One2many('mentorize.request', 'mahasiswa_id', string='Request Mentoring')