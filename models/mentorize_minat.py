from odoo import models, fields


class MentorizeMinat(models.Model):
    _name = 'mentorize.minat'
    _description = 'Minat Mentorize'

    name = fields.Char(
        string='Nama Minat',
        required=True
    )

    description = fields.Text(
        string='Deskripsi'
    )