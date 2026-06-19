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
    _order = 'tahun_selesai desc, tahun_mulai desc, tanggal desc, id desc'

    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni', required=True, ondelete='cascade')
    nama_experience = fields.Char(string='Nama Pengalaman', required=True)
    perusahaan = fields.Char(string='Perusahaan / Instansi')
    posisi = fields.Char(string='Posisi')
    tahun_mulai = fields.Char(string='Tahun Mulai')
    tahun_selesai = fields.Char(string='Tahun Selesai')
    tanggal = fields.Date(string='Tanggal Legacy')
    deskripsi = fields.Text(string='Deskripsi')

    def get_tahun_display(self):
        self.ensure_one()
        if self.tahun_mulai and self.tahun_selesai:
            return '%s - %s' % (self.tahun_mulai, self.tahun_selesai)
        return self.tahun_mulai or self.tahun_selesai or (self.tanggal and self.tanggal.strftime('%Y')) or ''
