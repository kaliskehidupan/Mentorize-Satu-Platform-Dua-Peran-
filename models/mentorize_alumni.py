from odoo import models, fields

class MentorizeAlumni(models.Model):
    _name = 'mentorize.alumni'
    _description = 'Profil Alumni/Mentor'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    name = fields.Char(related='user_id.name', string='Nama', readonly=True)
    kapa = fields.Char(string='KAPA')
    tempat_bekerja = fields.Char(string='Tempat Bekerja')
    pekerjaan = fields.Char(string='Pekerjaan')
    tahun_lulus = fields.Integer(string='Tahun Lulus')
    deskripsi = fields.Text(string='Deskripsi/Pengalaman')
    slot_mentoring = fields.Integer(string='Slot Mentoring', default=3)
    ketersediaan = fields.Selection([
        ('available', 'Tersedia'),
        ('busy', 'Sibuk'),
        ('offline', 'Offline'),
    ], string='Ketersediaan', default='available')
    skill_ids = fields.Many2many('mentorize.skill', string='Skill')
    experience_ids = fields.One2many('mentorize.experience', 'alumni_id', string='Pengalaman')
    is_verified = fields.Boolean(string='Terverifikasi', default=False)
    rating = fields.Float(string='Rating', compute='_compute_rating', store=True)

    def _compute_rating(self):
        for rec in self:
            feedbacks = self.env['mentorize.feedback'].search([('alumni_id', '=', rec.id)])
            if feedbacks:
                rec.rating = sum(feedbacks.mapped('rating')) / len(feedbacks)
            else:
                rec.rating = 0.0