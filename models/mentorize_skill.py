from odoo import models, fields


class MentorizeSkill(models.Model):
    _name = 'mentorize.skill'
    _description = 'Skill Mentorize'

    name = fields.Char(
        string='Nama Skill',
        required=True
    )

    description = fields.Text(
        string='Deskripsi'
    )