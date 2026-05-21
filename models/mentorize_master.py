from odoo import models, fields

class MentorizeMinat(models.Model):
    _name = 'mentorize.minat'
    _description = 'Minat'

    name = fields.Char(string='Nama Minat', required=True)


class MentorizeSkill(models.Model):
    _name = 'mentorize.skill'
    _description = 'Skill'

    name = fields.Char(string='Nama Skill', required=True)