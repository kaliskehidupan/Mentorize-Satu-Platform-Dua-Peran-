from odoo import api, models, fields


class MentorizeNotification(models.Model):
    _name = 'mentorize.notification'
    _description = 'Notifikasi Mentorize'
    _order = 'create_date desc'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade', index=True)
    title = fields.Char(string='Judul', required=True)
    message = fields.Text(string='Pesan')
    notif_type = fields.Selection([
        ('info', 'Info'),
        ('request_new', 'Request Baru'),
        ('request_approved', 'Request Diterima'),
        ('request_rejected', 'Request Ditolak'),
        ('session_end_requested', 'Pengajuan Sesi Selesai'),
        ('session_completed', 'Sesi Selesai'),
        ('chat', 'Chat'),
    ], default='info', string='Tipe')
    url = fields.Char(string='URL')
    is_read = fields.Boolean(string='Sudah Dibaca', default=False)

    @api.model
    def create_notification(self, user, title, message, notif_type='info', url=False):
        if not user:
            return False
        return self.create({
            'user_id': user.id,
            'title': title,
            'message': message,
            'notif_type': notif_type,
            'url': url or '',
        })
