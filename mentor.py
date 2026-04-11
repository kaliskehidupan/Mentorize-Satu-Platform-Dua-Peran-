from odoo import models, fields

class Mentor(models.Model):
    _name = 'mentoring.mentor'
    _description = 'Data Mentor'

    name = fields.Char(string="Nama", required=True)
    pekerjaan = fields.Char(string="Pekerjaan")
    pengalaman = fields.Text(string="Pengalaman")
    skill = fields.Text(string="Skill")