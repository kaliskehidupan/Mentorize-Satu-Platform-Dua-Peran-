from odoo import models, fields


class MentorizeSkillMinat(models.Model):
    _name = 'mentorize.skill.minat'
    _description = 'Skill dan Minat User'

    # ================= USER =================
    user_id = fields.Many2one(
        'res.users',
        string="User",
        required=True
    )

    # ================= SKILL =================
    skill_name = fields.Char(string="Skill", required=True)

    skill_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ], default='beginner')

    # ================= MINAT =================
    interest = fields.Char(string="Minat / Interest")