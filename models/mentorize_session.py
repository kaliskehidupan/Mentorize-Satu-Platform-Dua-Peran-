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
        ('reschedule_requested', 'Pengajuan Reschedule'),
        ('stop_requested', 'Pengajuan Berhenti'),
        ('stopped', 'Dihentikan'),
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

    completion_title = fields.Char(string='Judul Laporan Selesai')
    completion_method = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Metode Pelaksanaan')
    completion_summary = fields.Text(string='Ringkasan Pembahasan')
    material_discussed = fields.Text(string='Materi yang Dibahas')
    mentoring_result = fields.Text(string='Hasil / Insight Mentoring')
    follow_up_note = fields.Text(string='Catatan Tindak Lanjut')
    student_obstacle = fields.Text(string='Kendala Selama Mentoring')
    completion_feedback = fields.Text(string='Feedback untuk Mentor')
    completion_rating = fields.Integer(string='Rating Mentor', default=5)
    completion_requested_by = fields.Many2one('res.users', string='Pengaju Selesai', ondelete='set null')
    completion_approved_by = fields.Many2one('res.users', string='Penyetuju Selesai', ondelete='set null')

    stop_requested_by = fields.Many2one('res.users', string='Pengaju Berhenti', ondelete='set null')
    stop_reason = fields.Text(string='Alasan Berhenti')
    stop_requested_at = fields.Datetime(string='Pengajuan Berhenti Pada')
    stop_approved_by = fields.Many2one('res.users', string='Penyetuju Berhenti', ondelete='set null')
    stopped_at = fields.Datetime(string='Dihentikan Pada')

    reschedule_reason = fields.Text(string='Alasan Reschedule')
    reschedule_requested_at = fields.Datetime(string='Pengajuan Reschedule Pada')
