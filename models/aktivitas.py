from odoo import models, fields


class MentorizeActivity(models.Model):
    _name = 'mentorize.activity'
    _description = 'Aktivitas User'

    # ================= USER =================
    user_id = fields.Many2one(
        'res.users',
        string="User",
        required=True
    )

    # ================= JENIS AKTIVITAS =================
    activity_type = fields.Selection([
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('upload', 'Upload Laporan'),
        ('request', 'Request Mentoring'),
        ('action', 'Action Admin'),
    ], string="Jenis Aktivitas")

    # ================= DETAIL =================
    description = fields.Text(string="Deskripsi")

    # ================= WAKTU =================
    timestamp = fields.Datetime(
        string="Waktu",
        default=fields.Datetime.now
    )