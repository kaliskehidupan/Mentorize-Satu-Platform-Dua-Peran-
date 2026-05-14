from odoo import models, fields
from odoo.exceptions import UserError


class MentorizeRequest(models.Model):
    _name = 'mentorize.request'
    _description = 'Request Mentoring'

    mahasiswa_id = fields.Many2one(
        'mentorize.mahasiswa',
        string='Mahasiswa',
        required=True
    )

    alumni_id = fields.Many2one(
        'mentorize.alumni',
        string='Alumni/Mentor',
        required=True
    )

    topik = fields.Char(
        string='Topik Mentoring',
        required=True
    )

    deskripsi = fields.Text(
        string='Deskripsi/Catatan'
    )

    status = fields.Selection([
        ('pending', 'Menunggu'),
        ('approved', 'Diterima'),
        ('rejected', 'Ditolak'),
    ], string='Status', default='pending')

    tanggal_request = fields.Datetime(
        string='Tanggal Request',
        default=fields.Datetime.now
    )

    session_ids = fields.One2many(
        'mentorize.session',
        'request_id',
        string='Sesi'
    )

    room_chat_id = fields.Many2one(
        'mentorize.room.chat',
        string='Room Chat'
    )

    def action_approve(self):
        for rec in self:
            rec.status = 'approved'

            # Pastikan mahasiswa dan alumni punya relasi ke res.users
            if not rec.mahasiswa_id.user_id:
                raise UserError('Mahasiswa ini belum terhubung dengan user login.')

            if not rec.alumni_id.user_id:
                raise UserError('Alumni ini belum terhubung dengan user login.')

            existing_room = self.env['mentorize.room.chat'].sudo().search([
                ('request_id', '=', rec.id)
            ], limit=1)

            if not existing_room:
                existing_room = self.env['mentorize.room.chat'].sudo().create({
                    'name': 'Room Chat %s - %s' % (
                        rec.mahasiswa_id.name,
                        rec.alumni_id.name
                    ),
                    'request_id': rec.id,
                    'mahasiswa_id': rec.mahasiswa_id.user_id.id,
                    'alumni_id': rec.alumni_id.user_id.id,
                    'status': 'active',
                })

            rec.room_chat_id = existing_room.id

        return True

    def action_reject(self):
        for rec in self:
            rec.status = 'rejected'

        return True