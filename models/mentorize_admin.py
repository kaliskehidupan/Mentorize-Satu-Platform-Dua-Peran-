from odoo import api, models, fields


class MentorizeActivity(models.Model):
    _name = 'mentorize.activity'
    _description = 'Log Aktivitas Mentorize'
    _order = 'timestamp desc, id desc'

    user_id = fields.Many2one('res.users', string='User', ondelete='set null')
    activity_type = fields.Selection([
        ('login', 'Login'),
        ('profile', 'Update Profil'),
        ('request', 'Request Mentoring'),
        ('approval', 'Approval Mentoring'),
        ('session', 'Sesi Mentoring'),
        ('chat', 'Chat'),
        ('report', 'Laporan'),
        ('admin', 'Aksi Admin'),
    ], string='Jenis Aktivitas', default='admin', index=True)
    description = fields.Text(string='Deskripsi')
    related_model = fields.Char(string='Model Terkait')
    related_id = fields.Integer(string='ID Terkait')
    timestamp = fields.Datetime(string='Waktu', default=fields.Datetime.now, index=True)

    @api.model
    def log(self, user=False, activity_type='admin', description='', related_model=False, related_id=False):
        return self.sudo().create({
            'user_id': user.id if user else False,
            'activity_type': activity_type,
            'description': description or '',
            'related_model': related_model or '',
            'related_id': related_id or 0,
        })


class MentorizePelanggaran(models.Model):
    _name = 'mentorize.pelanggaran'
    _description = 'Laporan Pengguna Mentorize'
    _order = 'create_date desc, id desc'

    pelapor_id = fields.Many2one('res.users', string='Pelapor', required=True, ondelete='cascade', index=True)
    dilaporkan_id = fields.Many2one('res.users', string='User yang Dilaporkan', ondelete='set null', index=True)
    request_id = fields.Many2one('mentorize.request', string='Request Terkait', ondelete='set null')
    session_id = fields.Many2one('mentorize.session', string='Sesi Terkait', ondelete='set null')
    kategori = fields.Selection([
        ('perilaku', 'Perilaku Tidak Pantas'),
        ('jadwal', 'Masalah Jadwal'),
        ('chat', 'Masalah Chat'),
        ('tidak_respon', 'Tidak Merespons'),
        ('konten', 'Konten Tidak Sesuai'),
        ('teknis', 'Masalah Teknis'),
        ('lainnya', 'Lainnya'),
    ], string='Kategori', default='lainnya', required=True)
    judul = fields.Char(string='Judul Laporan', required=True)
    deskripsi = fields.Text(string='Deskripsi', required=True)
    attachment_id = fields.Many2one('ir.attachment', string='Bukti Gambar', ondelete='set null')
    attachment_name = fields.Char(string='Nama Bukti')
    attachment_mimetype = fields.Char(string='Tipe Bukti')
    attachment_size = fields.Integer(string='Ukuran Bukti')
    status = fields.Selection([
        ('baru', 'Baru'),
        ('diproses', 'Diproses'),
        ('selesai', 'Selesai'),
        ('ditolak', 'Ditolak'),
    ], string='Status', default='baru', index=True)
    admin_note = fields.Text(string='Catatan Admin')
    action = fields.Selection([
        ('none', 'Tanpa Sanksi'),
        ('warning', 'Peringatan'),
        ('disabled', 'Akun Dinonaktifkan'),
        ('ignored', 'Laporan Ditolak'),
    ], string='Tindakan', default='none')
    processed_by = fields.Many2one('res.users', string='Diproses Oleh', ondelete='set null')
    resolved_at = fields.Datetime(string='Selesai Pada')


class MentorizeLaporan(models.Model):
    _name = 'mentorize.laporan'
    _description = 'Review Laporan Akhir Mentoring'
    _order = 'create_date desc, id desc'

    session_id = fields.Many2one('mentorize.session', string='Sesi Mentoring', ondelete='cascade')
    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', ondelete='set null')
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni/Mentor', ondelete='set null')
    judul = fields.Char(string='Judul Laporan', required=True)
    ringkasan = fields.Text(string='Ringkasan')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending', index=True)
    admin_note = fields.Text(string='Catatan Admin')
