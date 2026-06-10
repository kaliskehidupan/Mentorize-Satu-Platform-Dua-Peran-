from odoo import models, fields


class MentorizeMinat(models.Model):
    _name = 'mentorize.minat'
    _description = 'Mentorize Minat'
    _order = 'name'

    name = fields.Char(string='Nama Minat', required=True)
    description = fields.Text(string='Deskripsi')


class MentorizeSkill(models.Model):
    _name = 'mentorize.skill'
    _description = 'Mentorize Skill'
    _order = 'name'

    name = fields.Char(string='Nama Skill', required=True)
    description = fields.Text(string='Deskripsi')


class MentorizeExperience(models.Model):
    _name = 'mentorize.experience'
    _description = 'Pengalaman Alumni'
    _order = 'tanggal desc, id desc'

    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni', required=True, ondelete='cascade')
    nama_experience = fields.Char(string='Nama Pengalaman', required=True)
    perusahaan = fields.Char(string='Perusahaan / Instansi')
    posisi = fields.Char(string='Posisi')
    tanggal = fields.Date(string='Tanggal')
    deskripsi = fields.Text(string='Deskripsi')
