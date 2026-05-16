from odoo import models, fields

class MentorizeMinat(models.Model):
    _name = 'mentorize.minat'
    _description = 'Minat'
    name = fields.Char(string='Nama Minat', required=True)

class MentorizeSkill(models.Model):
    _name = 'mentorize.skill'
    _description = 'Skill'
    name = fields.Char(string='Nama Skill', required=True)

class MentorizeExperience(models.Model):
    _name = 'mentorize.experience'
    _description = 'Pengalaman Alumni'
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni', required=True, ondelete='cascade')
    nama_experience = fields.Char(string='Nama Pengalaman', required=True)
    perusahaan = fields.Char(string='Perusahaan')
    posisi = fields.Char(string='Posisi')
    tanggal = fields.Date(string='Tanggal')
    deskripsi = fields.Text(string='Deskripsi')