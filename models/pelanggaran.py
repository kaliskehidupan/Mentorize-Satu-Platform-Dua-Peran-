from odoo import models, fields


class MentorizePelanggaran(models.Model):
    _name = 'mentorize.pelanggaran'
    _description = 'Laporan Pelanggaran User'

    # ================= USER YANG MELAPORKAN =================
    pelapor_id = fields.Many2one(
        'res.users',
        string="Pelapor",
        required=True
    )

    # ================= USER YANG DILAPORKAN =================
    dilaporkan_id = fields.Many2one(
        'res.users',
        string="User yang Dilaporkan",
        required=True
    )

    # ================= ISI LAPORAN =================
    alasan = fields.Char(string="Alasan", required=True)

    deskripsi = fields.Text(string="Deskripsi")

    # ================= STATUS ADMIN =================
    status = fields.Selection([
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('closed', 'Closed'),
    ], default='pending')

    # ================= ACTION ADMIN =================
    action = fields.Selection([
        ('none', 'None'),
        ('disabled', 'User Disabled'),
        ('ignored', 'Ignored'),
    ], default='none')