from odoo import models, fields
from odoo.exceptions import UserError

class MentorizeSession(models.Model):
    _name = 'mentorize.session'
    _description = 'Sesi Mentoring'
    _order = 'tanggal_mentoring desc'

    request_id = fields.Many2one(
        'mentorize.request',
        string='Request',
        required=True,
        ondelete='cascade'
    )
    tanggal_mentoring = fields.Datetime(
        string='Tanggal & Jam Sesi',
        required=True
    )
    durasi = fields.Integer(
        string='Durasi (menit)',
        default=60
    )
    mode = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Mode', default='offline')
    lokasi_link = fields.Char(string='Lokasi / Link Meeting')
    ringkasan_materi = fields.Text(string='Ringkasan Materi')
    status = fields.Selection([
        ('scheduled', 'Terjadwal'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan'),
        ('rescheduled', 'Dijadwalkan Ulang'),
    ], string='Status', default='scheduled')
    feedback_id = fields.Many2one('mentorize.feedback', string='Feedback')

    def action_complete(self):
        for session in self:
            if session.status == 'cancelled':
                raise UserError('Sesi yang sudah dibatalkan tidak bisa ditandai selesai.')
            session.status = 'completed'
            if session.request_id and 'status' in session.request_id._fields:
                session.request_id.status = 'completed'
        return True

    def action_cancel(self):
        for session in self:
            if session.status == 'completed':
                raise UserError('Sesi yang sudah selesai tidak bisa dibatalkan.')
            session.status = 'cancelled'
            if session.request_id and 'status' in session.request_id._fields:
                session.request_id.status = 'cancelled'
        return True

    def action_reschedule(self, tanggal_mentoring=None, lokasi_link=None, ringkasan_materi=None):
        for session in self:
            if session.status == 'completed':
                raise UserError('Sesi yang sudah selesai tidak bisa dijadwalkan ulang.')
            if session.status == 'cancelled':
                raise UserError('Sesi yang sudah dibatalkan tidak bisa dijadwalkan ulang.')
            vals = {'status': 'rescheduled'}
            if tanggal_mentoring:
                vals['tanggal_mentoring'] = tanggal_mentoring
            if lokasi_link:
                vals['lokasi_link'] = lokasi_link
            if ringkasan_materi:
                vals['ringkasan_materi'] = ringkasan_materi
            session.write(vals)
        return True