from odoo import models, fields


class MentorizeRoomChat(models.Model):
    _name = 'mentorize.roomchat'
    _description = 'Room Chat Mentoring'
    _order = 'write_date desc'

    request_id = fields.Many2one('mentorize.request', string='Pengajuan', ondelete='cascade')
    session_id = fields.Many2one('mentorize.session', string='Sesi', ondelete='set null')
    mahasiswa_user_id = fields.Many2one('res.users', string='User Mahasiswa')
    alumni_user_id = fields.Many2one('res.users', string='User Alumni')
    status = fields.Selection([
        ('active', 'Aktif'),
        ('closed', 'Ditutup'),
    ], string='Status', default='active')
    closed_reason = fields.Char(string='Alasan Ditutup')
    closed_at = fields.Datetime(string='Ditutup Pada')
    message_ids = fields.One2many('mentorize.message', 'room_id', string='Pesan')


class MentorizeMessage(models.Model):
    _name = 'mentorize.message'
    _description = 'Pesan Chat Mentorize'
    _order = 'waktu_kirim asc, id asc'

    room_id = fields.Many2one('mentorize.roomchat', string='Room', required=True, ondelete='cascade', index=True)
    sender_id = fields.Many2one('res.users', string='Pengirim', required=True, ondelete='cascade')
    isi_pesan = fields.Text(string='Isi Pesan')
    waktu_kirim = fields.Datetime(string='Waktu Kirim', default=fields.Datetime.now, index=True)

    # Lampiran chat disimpan di ir.attachment agar bisa berupa foto atau file.
    message_type = fields.Selection([
        ('text', 'Teks'),
        ('image', 'Gambar'),
        ('file', 'File'),
    ], string='Jenis Pesan', default='text')
    attachment_id = fields.Many2one('ir.attachment', string='Lampiran', ondelete='set null')
    attachment_name = fields.Char(string='Nama Lampiran')
    attachment_mimetype = fields.Char(string='Tipe Lampiran')
    attachment_size = fields.Integer(string='Ukuran Lampiran')

    def is_image_message(self):
        self.ensure_one()
        return (self.attachment_mimetype or '').startswith('image/')
