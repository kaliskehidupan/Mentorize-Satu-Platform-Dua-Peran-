from odoo import models, fields


class MentorizeSession(models.Model):
    _name = 'mentorize.session'
    _description = 'Sesi Mentoring'
    _order = 'tanggal_mentoring asc'

    request_id = fields.Many2one('mentorize.request', string='Request', required=True, ondelete='cascade')
    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True, ondelete='cascade')
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni / Mentor', required=True, ondelete='cascade')
    topik = fields.Char(string='Topik Mentoring')
    tanggal_mentoring = fields.Datetime(string='Tanggal & Jam Sesi', required=True)
    durasi = fields.Integer(string='Durasi (menit)', default=60)
    mode = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Mode', default='online')
    lokasi_link = fields.Char(string='Lokasi / Link Meeting')
    status = fields.Selection([
        ('scheduled', 'Terjadwal'),
        ('active', 'Berjalan'),
        ('end_requested', 'Pengajuan Selesai'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan'),
    ], string='Status', default='scheduled', index=True)
    end_request_note = fields.Text(string='Catatan Pengajuan Selesai')
    end_requested_at = fields.Datetime(string='Pengajuan Selesai Pada')
    completed_at = fields.Datetime(string='Selesai Pada')
    summary_saved = fields.Boolean(string='Rangkuman Disimpan', default=False)
    summary_topic = fields.Char(string='Judul Rangkuman')
    summary_learnings = fields.Text(string='Hal yang Dipelajari')
    summary_advice = fields.Text(string='Saran Mentor')
    summary_next_steps = fields.Text(string='Tindak Lanjut')
    summary_notes = fields.Text(string='Catatan Tambahan')
    feedback_id = fields.Many2one('mentorize.feedback', string='Feedback')
