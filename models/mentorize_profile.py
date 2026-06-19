from odoo import api, models, fields


class MentorizeMahasiswa(models.Model):
    _name = 'mentorize.mahasiswa'
    _description = 'Profil Mahasiswa Mentorize'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', index=True)
    name = fields.Char(related='user_id.name', string='Nama', readonly=True)
    email = fields.Char(related='user_id.email', string='Email', readonly=True)
    nim = fields.Char(string='NIM')
    jurusan = fields.Char(string='Jurusan / Program Studi')
    semester = fields.Integer(string='Semester')
    tujuan_karir = fields.Text(string='Tujuan Karir')
    bio = fields.Text(string='Bio Singkat')
    minat_ids = fields.Many2many('mentorize.minat', string='Minat')
    skill_ids = fields.Many2many('mentorize.skill', string='Skill')
    request_ids = fields.One2many('mentorize.request', 'mahasiswa_id', string='Request Mentoring')
    session_ids = fields.One2many('mentorize.session', 'mahasiswa_id', string='Sesi Mentoring')
    profile_complete = fields.Boolean(string='Profil Lengkap', compute='_compute_profile_complete')

    @api.depends('nim', 'jurusan', 'semester', 'tujuan_karir', 'bio', 'minat_ids', 'skill_ids', 'user_id.name', 'user_id.email', 'user_id.login')
    def _compute_profile_complete(self):
        for rec in self:
            login = (rec.user_id.login or '').strip()
            name = (rec.user_id.name or '').strip()
            email = (rec.user_id.email or '').strip()
            valid_identity = bool(name and name != login and email and '@' in email and email != login)
            rec.profile_complete = bool(
                valid_identity
                and rec.nim
                and rec.jurusan
                and rec.semester
                and rec.tujuan_karir
                and rec.bio
                and rec.minat_ids
                and rec.skill_ids
            )


class MentorizeAlumni(models.Model):
    _name = 'mentorize.alumni'
    _description = 'Profil Alumni / Mentor Mentorize'
    _order = 'id desc'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', index=True)
    name = fields.Char(related='user_id.name', string='Nama', readonly=True)
    email = fields.Char(related='user_id.email', string='Email', readonly=True)
    kapa = fields.Char(string='KAPA / ID Alumni')
    tempat_bekerja = fields.Char(string='Tempat Bekerja')
    pekerjaan = fields.Char(string='Pekerjaan')
    tahun_lulus = fields.Integer(string='Tahun Lulus')
    deskripsi = fields.Text(string='Deskripsi / Pengalaman')
    availability = fields.Selection([
        ('available', 'Tersedia'),
        ('busy', 'Sibuk'),
        ('offline', 'Offline'),
    ], string='Ketersediaan', default='available')
    slot_mentoring = fields.Integer(string='Slot Mentoring', default=3)
    minat_ids = fields.Many2many('mentorize.minat', string='Bidang Mentoring')
    skill_ids = fields.Many2many('mentorize.skill', string='Skill')
    experience_ids = fields.One2many('mentorize.experience', 'alumni_id', string='Pengalaman')
    is_verified = fields.Boolean(string='Terverifikasi Data', default=False)
    request_ids = fields.One2many('mentorize.request', 'alumni_id', string='Request Mentoring')
    session_ids = fields.One2many('mentorize.session', 'alumni_id', string='Sesi Mentoring')
    rating = fields.Float(string='Rating', compute='_compute_rating')
    profile_complete = fields.Boolean(string='Profil Lengkap', compute='_compute_profile_complete')

    def _compute_rating(self):
        Feedback = self.env['mentorize.feedback'].sudo()
        for rec in self:
            feedbacks = Feedback.search([('alumni_id', '=', rec.id)])
            rec.rating = round(sum(feedbacks.mapped('rating')) / len(feedbacks), 1) if feedbacks else 0.0

    @api.depends('kapa', 'tempat_bekerja', 'pekerjaan', 'deskripsi', 'skill_ids', 'minat_ids', 'experience_ids', 'experience_ids.perusahaan', 'experience_ids.posisi', 'experience_ids.tahun_mulai', 'experience_ids.tahun_selesai', 'experience_ids.tanggal', 'user_id.name', 'user_id.email', 'user_id.login')
    def _compute_profile_complete(self):
        for rec in self:
            login = (rec.user_id.login or '').strip()
            name = (rec.user_id.name or '').strip()
            email = (rec.user_id.email or '').strip()
            valid_identity = bool(name and name != login and email and '@' in email and email != login)
            complete_experiences = rec.experience_ids.filtered(
                lambda exp: exp.perusahaan and exp.posisi and (exp.tahun_mulai or exp.tahun_selesai or exp.tanggal)
            )
            rec.profile_complete = bool(
                valid_identity
                and rec.kapa
                and rec.tempat_bekerja
                and rec.pekerjaan
                and rec.deskripsi
                and rec.skill_ids
                and rec.minat_ids
                and len(complete_experiences) >= 3
            )
