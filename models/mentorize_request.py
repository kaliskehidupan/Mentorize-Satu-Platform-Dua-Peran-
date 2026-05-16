from odoo import api, models, fields


class MentorizeRequest(models.Model):
    _name = 'mentorize.request'
    _description = 'Request Mentoring'
    _order = 'create_date desc'

    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True, ondelete='cascade', index=True)
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni / Mentor', required=True, ondelete='cascade', index=True)
    topik = fields.Char(string='Topik Mentoring', required=True)
    deskripsi = fields.Text(string='Deskripsi / Catatan')
    requested_datetime = fields.Datetime(string='Tanggal & Jam Diajukan', required=True)
    status = fields.Selection([
        ('pending', 'Menunggu'),
        ('approved', 'Diterima'),
        ('rejected', 'Ditolak'),
        ('done', 'Selesai'),
    ], string='Status', default='pending', index=True)
    tanggal_request = fields.Datetime(string='Tanggal Request', default=fields.Datetime.now)
    session_ids = fields.One2many('mentorize.session', 'request_id', string='Sesi')
    room_chat_id = fields.Many2one('mentorize.roomchat', string='Room Chat')

    def action_approve(self):
        Session = self.env['mentorize.session'].sudo()
        Room = self.env['mentorize.roomchat'].sudo()
        Notification = self.env['mentorize.notification'].sudo()
        for rec in self:
            rec.status = 'approved'
            session = Session.search([('request_id', '=', rec.id)], limit=1)
            if not session:
                session = Session.create({
                    'request_id': rec.id,
                    'mahasiswa_id': rec.mahasiswa_id.id,
                    'alumni_id': rec.alumni_id.id,
                    'tanggal_mentoring': rec.requested_datetime,
                    'topik': rec.topik,
                    'status': 'scheduled',
                })
            room = rec.room_chat_id
            if not room:
                room = Room.create({
                    'request_id': rec.id,
                    'session_id': session.id,
                    'mahasiswa_user_id': rec.mahasiswa_id.user_id.id,
                    'alumni_user_id': rec.alumni_id.user_id.id,
                    'status': 'active',
                })
                rec.room_chat_id = room.id
            else:
                room.write({'session_id': session.id, 'status': 'active'})
            Notification.create_notification(
                rec.mahasiswa_id.user_id,
                'Request mentoring diterima',
                'Request mentoring dengan %s telah diterima. Room chat sudah aktif.' % (rec.alumni_id.name or 'mentor'),
                notif_type='request_approved',
                url='/chat?room_id=%s' % room.id,
            )
        return True

    def action_reject(self):
        Notification = self.env['mentorize.notification'].sudo()
        for rec in self:
            rec.status = 'rejected'
            Notification.create_notification(
                rec.mahasiswa_id.user_id,
                'Request mentoring ditolak',
                'Request mentoring dengan %s ditolak. Kamu bisa membuat request baru.' % (rec.alumni_id.name or 'mentor'),
                notif_type='request_rejected',
                url='/mentors',
            )
        return True
