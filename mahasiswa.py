from odoo import models, fields

class Mahasiswa(models.Model):
    _name = 'mentoring.mahasiswa'
    _description = 'Data Mahasiswa'

    name = fields.Char(string="Nama", required=True)
    nim = fields.Char(string="NIM")
    jurusan = fields.Char(string="Jurusan")
    minat = fields.Text(string="Minat")
    tujuan_karir = fields.Text(string="Tujuan Karir")