from odoo import models, fields


class MentorizeLaporan(models.Model):
    _name = 'mentorize.laporan'
    _description = 'Laporan Akhir Mahasiswa'

    # ================= RELASI =================
    mahasiswa_id = fields.Many2one(
        'res.users',
        string="Mahasiswa",
        required=True
    )

    # ================= DATA LAPORAN =================
    judul = fields.Char(string="Judul Laporan", required=True)

    file = fields.Binary(string="File Laporan")

    filename = fields.Char(string="Nama File")

    # ================= STATUS REVIEW ADMIN =================
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending')

    # ================= TRACKING =================
    create_date = fields.Datetime(string="Tanggal Upload", readonly=True)