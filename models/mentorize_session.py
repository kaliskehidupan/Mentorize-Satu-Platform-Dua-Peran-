from datetime import timedelta

from odoo import api, models, fields


class MentorizeSession(models.Model):
    _name = 'mentorize.session'
    _description = 'Sesi Mentoring'
    _order = 'tanggal_mentoring asc'

    # Relasi utama sesi mentoring.
    request_id = fields.Many2one('mentorize.request', string='Pengajuan', required=True, ondelete='cascade')
    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True, ondelete='cascade')
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni / Mentor', required=True, ondelete='cascade')
    topik = fields.Char(string='Topik Mentoring')

    # Jadwal sesi. Satu sesi aktif selama 2 x 24 jam dari tanggal_mentoring.
    tanggal_mentoring = fields.Datetime(string='Tanggal & Jam Mulai Sesi', required=True, index=True)
    durasi = fields.Integer(string='Durasi (menit)', default=60)
    duration_hours = fields.Integer(string='Batas Waktu Sesi (jam)', default=48)
    started_at = fields.Datetime(string='Sesi Dimulai Pada')
    expired_at = fields.Datetime(string='Batas Akhir Sesi')
    session_end_at = fields.Datetime(string='Tanggal Selesai Kalender', index=True)

    mode = fields.Selection([
        ('online', 'Online'),
        ('offline', 'Offline'),
    ], string='Mode', default='online')
    lokasi_link = fields.Char(string='Lokasi / Link Meeting')

    # Status lifecycle sesi.
    status = fields.Selection([
        ('scheduled', 'Terjadwal'),
        ('active', 'Aktif'),
        ('time_expired', 'Waktu Habis'),
        ('extension_pending', 'Pengajuan Tambah Waktu'),
        ('extended', 'Diperpanjang'),
        ('end_requested', 'Pengajuan Selesai'),
        ('completed', 'Selesai'),
        ('cancelled', 'Dibatalkan'),
        ('reschedule_requested', 'Pengajuan Ubah Jadwal'),
        ('stop_requested', 'Pengajuan Berhenti'),
        ('stopped', 'Dihentikan'),
    ], string='Status', default='scheduled', index=True)

    # Data pengajuan tambah waktu.
    extension_requested_datetime = fields.Datetime(string='Tanggal Tambahan Diajukan')
    extension_note = fields.Text(string='Catatan Tambah Waktu')
    extension_requested_by = fields.Many2one('res.users', string='Pengaju Tambah Waktu', ondelete='set null')
    extension_requested_at = fields.Datetime(string='Pengajuan Tambah Waktu Pada')
    extension_approved_by = fields.Many2one('res.users', string='Penyetuju Tambah Waktu', ondelete='set null')
    extension_approved_at = fields.Datetime(string='Tambah Waktu Disetujui Pada')
    extension_rejected_at = fields.Datetime(string='Tambah Waktu Ditolak Pada')

    # Data pengajuan selesai.
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

    # Laporan hasil mentoring dari mahasiswa.
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
    completion_feedback = fields.Text(string='Umpan Balik untuk Mentor')
    completion_rating = fields.Integer(string='Rating Mentor', default=5)
    completion_requested_by = fields.Many2one('res.users', string='Pengaju Selesai', ondelete='set null')
    completion_approved_by = fields.Many2one('res.users', string='Penyetuju Selesai', ondelete='set null')

    # Data pengajuan berhenti.
    stop_requested_by = fields.Many2one('res.users', string='Pengaju Berhenti', ondelete='set null')
    stop_reason = fields.Text(string='Alasan Berhenti')
    stop_requested_at = fields.Datetime(string='Pengajuan Berhenti Pada')
    stop_approved_by = fields.Many2one('res.users', string='Penyetuju Berhenti', ondelete='set null')
    stopped_at = fields.Datetime(string='Dihentikan Pada')

    # Data ubah jadwal.
    reschedule_reason = fields.Text(string='Alasan Ubah Jadwal')
    reschedule_requested_at = fields.Datetime(string='Pengajuan Ubah Jadwal Pada')

    @api.model_create_multi
    def create(self, vals_list):
        """Saat sesi dibuat, hitung otomatis rentang kalender 2 x 24 jam."""
        for vals in vals_list:
            tanggal = vals.get('tanggal_mentoring')
            hours = vals.get('duration_hours') or 48
            if tanggal and not vals.get('session_end_at'):
                dt = fields.Datetime.to_datetime(tanggal)
                vals['session_end_at'] = dt + timedelta(hours=hours)
        return super().create(vals_list)

    def write(self, vals):
        """Jika tanggal mulai berubah, perbarui batas kalendernya tanpa memicu rekursi."""
        if self.env.context.get('skip_session_end_update'):
            return super().write(vals)
        res = super().write(vals)
        if 'tanggal_mentoring' in vals or 'duration_hours' in vals:
            for rec in self:
                if rec.tanggal_mentoring and rec.status not in ['completed', 'cancelled', 'stopped']:
                    end_dt = rec.tanggal_mentoring + timedelta(hours=rec.duration_hours or 48)
                    rec.with_context(skip_session_end_update=True).write({'session_end_at': end_dt})
        return res

    def _activate_session(self):
        """Mengaktifkan sesi ketika tanggal mulai sudah tiba."""
        Notification = self.env['mentorize.notification'].sudo()
        now = fields.Datetime.now()
        for rec in self:
            if rec.status not in ['scheduled', 'extended']:
                continue
            start_dt = rec.tanggal_mentoring or now
            expired_dt = start_dt + timedelta(hours=rec.duration_hours or 48)
            rec.write({
                'status': 'active',
                'started_at': start_dt,
                'expired_at': expired_dt,
                'session_end_at': expired_dt,
            })
            if rec.request_id.room_chat_id:
                rec.request_id.room_chat_id.write({'status': 'active'})
            for target in [rec.mahasiswa_id.user_id, rec.alumni_id.user_id]:
                if target:
                    Notification.create_notification(
                        target,
                        'Sesi mentoring dimulai',
                        'Sesi mentoring "%s" sudah dimulai. Chat aktif selama 2 x 24 jam.' % (rec.topik or 'Mentoring'),
                        notif_type='session_started',
                        url='/chat?room_id=%s' % (rec.request_id.room_chat_id.id if rec.request_id.room_chat_id else ''),
                    )
        return True

    @api.model
    def _cron_update_session_status(self):
        """Cron otomatis untuk mulai sesi dan memberi peringatan saat 2 x 24 jam habis."""
        now = fields.Datetime.now()
        Notification = self.env['mentorize.notification'].sudo()

        # Sesi terjadwal otomatis aktif ketika tanggal mulai sudah tiba.
        scheduled = self.sudo().search([
            ('status', 'in', ['scheduled', 'extended']),
            ('tanggal_mentoring', '<=', now),
        ])
        scheduled._activate_session()

        # Sesi aktif otomatis masuk status waktu habis ketika melewati expired_at.
        expired = self.sudo().search([
            ('status', '=', 'active'),
            ('expired_at', '!=', False),
            ('expired_at', '<=', now),
        ])
        for rec in expired:
            rec.write({'status': 'time_expired'})
            for target in [rec.mahasiswa_id.user_id, rec.alumni_id.user_id]:
                if target:
                    Notification.create_notification(
                        target,
                        'Waktu mentoring habis',
                        'Waktu sesi "%s" sudah habis. Ajukan tambah waktu atau ajukan penyelesaian sesi.' % (rec.topik or 'Mentoring'),
                        notif_type='session_expired',
                        url='/chat?room_id=%s' % (rec.request_id.room_chat_id.id if rec.request_id.room_chat_id else ''),
                    )
        return True
