from odoo import http
from odoo import fields as odoo_fields
from odoo.http import request


class MentorizeController(http.Controller):
    """Website controller untuk halaman publik, auth, dashboard, dan profil Mentorize."""

    # =====================
    # HELPERS
    # =====================
    def _is_logged_in(self):
        return bool(request.env.user and not request.env.user._is_public())

    def _current_role(self):
        return request.env.user.sudo().mentorize_role or ''

    def _dashboard_redirect(self):
        role = self._current_role()
        if role == 'alumni':
            return request.redirect('/alumni/dashboard')
        if role == 'admin':
            return request.redirect('/admin/dashboard')
        return request.redirect('/dashboard')

    def _ensure_mahasiswa(self):
        user = request.env.user.sudo()
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not mahasiswa:
            mahasiswa = request.env['mentorize.mahasiswa'].sudo().create({
                'user_id': user.id,
                'nim': user.nim or '-',
                'jurusan': user.jurusan or '',
                'tujuan_karir': user.tujuan_karir or '',
            })
        return mahasiswa

    def _ensure_alumni(self):
        user = request.env.user.sudo()
        alumni = request.env['mentorize.alumni'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not alumni:
            alumni = request.env['mentorize.alumni'].sudo().create({
                'user_id': user.id,
                'kapa': user.kapa or '-',
            })
        return alumni

    def _login_error_message(self, code):
        messages = {
            '1': 'Email atau password salah. Silakan coba lagi.',
            'role': 'Role yang dipilih tidak sesuai dengan akun Anda.',
            'identity': 'NIM/KAPA tidak sesuai dengan akun Anda.',
            'required': 'Email dan password wajib diisi.',
        }
        return messages.get(code or '', '')

    def _assign_role_group(self, user, role):
        group_xmlid = {
            'mahasiswa': 'mentorize.group_mentorize_mahasiswa',
            'alumni': 'mentorize.group_mentorize_alumni',
            'admin': 'mentorize.group_mentorize_admin',
        }.get(role)
        if group_xmlid:
            user.sudo().write({'groups_id': [(4, request.env.ref(group_xmlid).id)]})

    def _get_recommended_mentors(self, mahasiswa, limit=4):
        Alumni = request.env['mentorize.alumni'].sudo()
        domain = [('ketersediaan', '=', 'available')]
        alumni_pool = Alumni.search(domain, limit=40)
        if not alumni_pool:
            alumni_pool = Alumni.search([], limit=40)

        student_skills = set(mahasiswa.skill_ids.ids)
        scored = []
        for alumni in alumni_pool:
            mentor_skills = set(alumni.skill_ids.ids)
            score = len(student_skills & mentor_skills)
            scored.append((score, alumni))
        scored.sort(key=lambda item: (item[0], item[1].rating or 0), reverse=True)
        return [alumni for _, alumni in scored[:limit]]

    # =====================
    # PUBLIC / AUTH ROUTES
    # =====================
    @http.route(['/', '/mentorize'], type='http', auth='public', website=True)
    def landing(self, **kwargs):
        if self._is_logged_in():
            return self._dashboard_redirect()
        return request.render('mentorize.page_landing')

    @http.route(['/login', '/mentorize/login'], type='http', auth='public', website=True)
    def login(self, **kwargs):
        if self._is_logged_in():
            return self._dashboard_redirect()
        return request.render('mentorize.page_login', {
            'error': self._login_error_message(kwargs.get('error')),
        })

    @http.route(['/login/submit', '/mentorize/login/submit'], type='http', auth='public', website=True, methods=['POST'])
    def login_submit(self, **kwargs):
        email = (kwargs.get('email') or '').strip()
        password = kwargs.get('password') or ''
        role = kwargs.get('role') or 'mahasiswa'
        identity = (kwargs.get('identity') or '').strip()

        if not email or not password:
            return request.redirect('/login?error=required')

        try:
            uid = request.session.authenticate(request.db, email, password)
        except Exception:
            uid = False

        if not uid:
            return request.redirect('/login?error=1')

        user = request.env['res.users'].sudo().browse(uid)
        if user.mentorize_role and user.mentorize_role != role:
            request.session.logout(keep_db=True)
            return request.redirect('/login?error=role')

        if role == 'mahasiswa':
            mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([('user_id', '=', user.id)], limit=1)
            valid_identity = user.nim or (mahasiswa.nim if mahasiswa else '')
            if identity and valid_identity and identity != valid_identity:
                request.session.logout(keep_db=True)
                return request.redirect('/login?error=identity')
        elif role == 'alumni':
            alumni = request.env['mentorize.alumni'].sudo().search([('user_id', '=', user.id)], limit=1)
            valid_identity = user.kapa or (alumni.kapa if alumni else '')
            if identity and valid_identity and identity != valid_identity:
                request.session.logout(keep_db=True)
                return request.redirect('/login?error=identity')

        return request.redirect('/dashboard' if role == 'mahasiswa' else '/alumni/dashboard')

    @http.route(['/register', '/mentorize/register'], type='http', auth='public', website=True)
    def register(self, **kwargs):
        if self._is_logged_in():
            return self._dashboard_redirect()
        return request.render('mentorize.page_register', {
            'error': kwargs.get('error') or '',
        })

    @http.route(['/register/submit', '/mentorize/register/submit'], type='http', auth='public', website=True, methods=['POST'])
    def register_submit(self, **kwargs):
        name = (kwargs.get('name') or '').strip()
        email = (kwargs.get('email') or '').strip()
        password = kwargs.get('password') or ''
        confirm_password = kwargs.get('confirm_password') or ''
        role = kwargs.get('role') or 'mahasiswa'
        identity = (kwargs.get('identity') or '').strip()

        if not name or not email or not password or not identity:
            return request.render('mentorize.page_register', {
                'error': 'Nama, email, identitas, dan password wajib diisi.',
            })
        if password != confirm_password:
            return request.render('mentorize.page_register', {
                'error': 'Password dan konfirmasi password tidak sama.',
            })
        existing = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if existing:
            return request.render('mentorize.page_register', {
                'error': 'Email sudah terdaftar. Gunakan email lain atau langsung login.',
            })

        try:
            user_vals = {
                'name': name,
                'login': email,
                'email': email,
                'password': password,
                'mentorize_role': role,
                'is_verified': False,
            }
            if role == 'mahasiswa':
                user_vals['nim'] = identity
            else:
                user_vals['kapa'] = identity

            new_user = request.env['res.users'].sudo().with_context(no_reset_password=True).create(user_vals)
            self._assign_role_group(new_user, role)

            if role == 'mahasiswa':
                request.env['mentorize.mahasiswa'].sudo().create({
                    'user_id': new_user.id,
                    'nim': identity,
                })
            else:
                request.env['mentorize.alumni'].sudo().create({
                    'user_id': new_user.id,
                    'kapa': identity,
                })

            uid = request.session.authenticate(request.db, email, password)
            if uid:
                return request.redirect('/dashboard' if role == 'mahasiswa' else '/alumni/dashboard')
        except Exception as e:
            return request.render('mentorize.page_register', {
                'error': 'Terjadi kesalahan saat membuat akun: %s' % e,
            })

        return request.redirect('/login')

    @http.route(['/forgot-password', '/mentorize/forgot-password'], type='http', auth='public', website=True)
    def forgot_password(self, **kwargs):
        return request.render('mentorize.page_forgot_password')

    @http.route(['/forgot-password/submit', '/mentorize/forgot-password/submit'], type='http', auth='public', website=True, methods=['POST'])
    def forgot_password_submit(self, **kwargs):
        email = (kwargs.get('email') or '').strip()
        user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if not user:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Email tidak ditemukan.',
            })
        try:
            user.sudo().action_reset_password()
            return request.render('mentorize.page_forgot_password', {
                'success': True,
            })
        except Exception:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Gagal mengirim email. Pastikan konfigurasi outgoing email Odoo sudah aktif.',
            })

    # =====================
    # MAHASISWA ROUTES
    # =====================
    @http.route(['/dashboard', '/mentorize/mahasiswa/dashboard'], type='http', auth='user', website=True)
    def dashboard_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/alumni/dashboard')
        if self._current_role() == 'admin':
            return request.redirect('/admin/dashboard')

        user = request.env.user.sudo()
        mahasiswa = self._ensure_mahasiswa()

        mentoring_aktif = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'approved'),
        ], order='tanggal_request desc')

        pending_requests = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'pending'),
        ], order='tanggal_request desc', limit=5)

        jadwal_terdekat = request.env['mentorize.session'].sudo().search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'scheduled'),
        ], order='tanggal_mentoring asc', limit=5)

        riwayat_mentoring = request.env['mentorize.session'].sudo().search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', 'in', ['completed', 'cancelled', 'rescheduled']),
        ], order='tanggal_mentoring desc', limit=5)

        rekomendasi = self._get_recommended_mentors(mahasiswa, limit=4)

        sesi_berjalan = request.env['mentorize.session'].sudo().search_count([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'scheduled'),
        ])
        sesi_selesai = request.env['mentorize.session'].sudo().search_count([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'completed'),
        ])
        total_sesi = sesi_berjalan + sesi_selesai
        progress_pct = round((sesi_selesai / total_sesi * 100)) if total_sesi else 0

        stats = {
            'mentor_aktif': len(mentoring_aktif),
            'sesi_berjalan': sesi_berjalan,
            'sesi_selesai': sesi_selesai,
            'progress_pct': progress_pct,
            'request_pending': len(pending_requests),
        }

        return request.render('mentorize.dashboard_mahasiswa', {
            'user': user,
            'mahasiswa': mahasiswa,
            'mentoring_aktif': mentoring_aktif,
            'pending_requests': pending_requests,
            'jadwal_terdekat': jadwal_terdekat,
            'riwayat_mentoring': riwayat_mentoring,
            'rekomendasi': rekomendasi,
            'stats': stats,
        })

    @http.route(['/profile', '/mentorize/mahasiswa/profil'], type='http', auth='user', website=True)
    def profil_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/alumni/dashboard')
        mahasiswa = self._ensure_mahasiswa()
        profil_lengkap = bool(
            mahasiswa.nim and mahasiswa.jurusan and mahasiswa.semester and
            mahasiswa.tujuan_karir and mahasiswa.minat_ids and mahasiswa.skill_ids
        )
        return request.render('mentorize.page_profil_mahasiswa', {
            'user': request.env.user.sudo(),
            'mahasiswa': mahasiswa,
            'profil_lengkap': profil_lengkap,
            'success': kwargs.get('success'),
        })

    @http.route(['/profile/edit', '/mentorize/mahasiswa/profil/edit'], type='http', auth='user', website=True)
    def edit_profil_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/alumni/dashboard')
        mahasiswa = self._ensure_mahasiswa()
        all_minat = request.env['mentorize.minat'].sudo().search([], order='name asc')
        all_skill = request.env['mentorize.skill'].sudo().search([], order='name asc')
        return request.render('mentorize.page_edit_profil_mahasiswa', {
            'user': request.env.user.sudo(),
            'mahasiswa': mahasiswa,
            'all_minat': all_minat,
            'all_skill': all_skill,
            'selected_minat_ids': mahasiswa.minat_ids.ids,
            'selected_skill_ids': mahasiswa.skill_ids.ids,
        })

    @http.route(['/profile/update', '/mentorize/mahasiswa/profil/update'], type='http', auth='user', website=True, methods=['POST'])
    def update_profil_mahasiswa(self, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        user = request.env.user.sudo()
        try:
            semester = kwargs.get('semester') or '0'
            tujuan_karir = kwargs.get('tujuan_karir') or ''
            minat_ids = [int(x) for x in request.httprequest.form.getlist('minat_ids') if x]
            skill_ids = [int(x) for x in request.httprequest.form.getlist('skill_ids') if x]

            user.write({
                'name': kwargs.get('name') or user.name,
                'nim': kwargs.get('nim') or user.nim,
                'jurusan': kwargs.get('jurusan') or user.jurusan,
                'tujuan_karir': tujuan_karir,
            })
            mahasiswa.write({
                'nim': kwargs.get('nim') or mahasiswa.nim,
                'jurusan': kwargs.get('jurusan') or '',
                'semester': int(semester) if semester.isdigit() else 0,
                'tujuan_karir': tujuan_karir,
                'minat_ids': [(6, 0, minat_ids)],
                'skill_ids': [(6, 0, skill_ids)],
            })
            return request.redirect('/profile?success=1')
        except Exception as e:
            return request.render('mentorize.page_edit_profil_mahasiswa', {
                'user': user,
                'mahasiswa': mahasiswa,
                'all_minat': request.env['mentorize.minat'].sudo().search([], order='name asc'),
                'all_skill': request.env['mentorize.skill'].sudo().search([], order='name asc'),
                'selected_minat_ids': mahasiswa.minat_ids.ids,
                'selected_skill_ids': mahasiswa.skill_ids.ids,
                'error': 'Terjadi kesalahan: %s' % e,
            })

    @http.route(['/mentors', '/mentorize/mahasiswa/cari-mentor'], type='http', auth='user', website=True)
    def mentors(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/alumni/dashboard')
        mahasiswa = self._ensure_mahasiswa()
        query = (kwargs.get('q') or '').strip()
        domain = []
        if query:
            domain = ['|', '|', ('name', 'ilike', query), ('pekerjaan', 'ilike', query), ('tempat_bekerja', 'ilike', query)]
        alumni = request.env['mentorize.alumni'].sudo().search(domain, order='rating desc, id desc', limit=30)
        return request.render('mentorize.page_mentors', {
            'user': request.env.user.sudo(),
            'mahasiswa': mahasiswa,
            'alumni_list': alumni,
            'query': query,
        })

    @http.route(['/mentors/<int:alumni_id>/request', '/mentorize/mentors/<int:alumni_id>/request'], type='http', auth='user', website=True, methods=['POST'])
    def request_mentor(self, alumni_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        alumni = request.env['mentorize.alumni'].sudo().browse(alumni_id)

        if not alumni.exists():
            return request.redirect('/mentors')

        existing = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('alumni_id', '=', alumni.id),
            ('status', 'in', ['pending', 'approved']),
        ], limit=1)

        if not existing:
            req = request.env['mentorize.request'].sudo().create({
                'mahasiswa_id': mahasiswa.id,
                'alumni_id': alumni.id,
                'topik': kwargs.get('topik') or 'Mentoring karier dan pengembangan skill',
                'deskripsi': kwargs.get('deskripsi') or '',
            })

            room = request.env['mentorize.roomchat'].sudo().create({
                'request_id': req.id
            })

            req.write({
                'room_chat_id': room.id
            })

        return request.redirect('/mentorize/mahasiswa/sesi')
    

    @http.route(['/mahasiswa/sesi', '/mentorize/mahasiswa/sesi'], type='http', auth='user', website=True)
    def sesi_mentoring_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/mentorize/alumni/sesi')

        user = request.env.user.sudo()
        mahasiswa = self._ensure_mahasiswa()

        Session = request.env['mentorize.session'].sudo()
        RequestMentoring = request.env['mentorize.request'].sudo()

        now = odoo_fields.Datetime.now()

        # request yang sudah disetujui alumni, untuk dropdown Ajukan Jadwal
        approved_requests = RequestMentoring.search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'approved'),
        ], order='tanggal_request desc')

        # jadwal mendatang
        upcoming_sessions = Session.search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', 'in', ['scheduled', 'rescheduled']),
            ('tanggal_mentoring', '>=', now),
        ], order='tanggal_mentoring asc')

        # sesi berjalan
        active_sessions = Session.search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'scheduled'),
            ('tanggal_mentoring', '<=', now),
        ], order='tanggal_mentoring asc')

        # riwayat
        history_sessions = Session.search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', 'in', ['completed', 'cancelled']),
        ], order='tanggal_mentoring desc')

        return request.render('mentorize.page_sesi_mentoring_mahasiswa', {
            'user': user,
            'mahasiswa': mahasiswa,
            'approved_requests': approved_requests,
            'upcoming_sessions': upcoming_sessions,
            'active_sessions': active_sessions,
            'history_sessions': history_sessions,
        })
    
    @http.route('/mentorize/mahasiswa/sesi/ajukan', type='http', auth='user', website=True, methods=['POST'])
    def ajukan_jadwal_mahasiswa(self, **kwargs):
        mahasiswa = self._ensure_mahasiswa()

        req_id = int(kwargs.get('request_id') or 0)
        req = request.env['mentorize.request'].sudo().browse(req_id)

        if not req.exists() or req.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/mentorize/mahasiswa/sesi')

        tanggal = kwargs.get('tanggal_mentoring') or ''
        tanggal = tanggal.replace('T', ' ')

        request.env['mentorize.session'].sudo().create({
            'request_id': req.id,
            'tanggal_mentoring': tanggal,
            'durasi': int(kwargs.get('durasi') or 60),
            'mode': kwargs.get('mode') or 'online',
            'lokasi_link': kwargs.get('lokasi_link') or '',
            'ringkasan_materi': kwargs.get('ringkasan_materi') or '',
            'status': 'scheduled',
        })

        return request.redirect('/mentorize/mahasiswa/sesi')
    
    @http.route('/mentorize/session/<int:session_id>/cancel', type='http', auth='user', website=True, methods=['POST'])
    def cancel_session_mahasiswa(self, session_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()

        sesi = request.env['mentorize.session'].sudo().browse(session_id)

        if sesi.exists() and sesi.request_id.mahasiswa_id.id == mahasiswa.id:
            sesi.write({
                'status': 'cancelled'
            })

        return request.redirect('/mentorize/mahasiswa/sesi')
    
    @http.route('/mentorize/session/<int:session_id>/reschedule', type='http', auth='user', website=True, methods=['POST'])
    def reschedule_session_mahasiswa(self, session_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()

        sesi = request.env['mentorize.session'].sudo().browse(session_id)

        if sesi.exists() and sesi.request_id.mahasiswa_id.id == mahasiswa.id:
            tanggal = kwargs.get('tanggal_mentoring')

            if tanggal:
                tanggal = tanggal.replace('T', ' ')

            sesi.write({
                'tanggal_mentoring': tanggal,
                'ringkasan_materi': kwargs.get('ringkasan_materi') or sesi.ringkasan_materi,
                'status': 'rescheduled',
            })

        return request.redirect('/mentorize/mahasiswa/sesi')


    @http.route('/mentorize/session/<int:session_id>/complete', type='http', auth='user', website=True, methods=['POST'])
    def complete_session_mahasiswa(self, session_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()

        sesi = request.env['mentorize.session'].sudo().browse(session_id)

        if sesi.exists() and sesi.request_id.mahasiswa_id.id == mahasiswa.id:
            sesi.write({
                'status': 'completed'
            })

        return request.redirect('/mentorize/mahasiswa/sesi')



    # =====================
    # ALUMNI ROUTES
    # =====================
    @http.route(['/alumni/dashboard', '/mentorize/alumni/dashboard'], type='http', auth='user', website=True)
    def dashboard_alumni(self, **kwargs):
        user = request.env.user.sudo()
        alumni = self._ensure_alumni()

        requests_list = request.env['mentorize.request'].sudo().search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'pending'),
        ], order='tanggal_request desc', limit=10)

        sesi_aktif = request.env['mentorize.session'].sudo().search_count([
            ('request_id.alumni_id', '=', alumni.id),
            ('status', '=', 'scheduled'),
        ])
        sesi_selesai = request.env['mentorize.session'].sudo().search_count([
            ('request_id.alumni_id', '=', alumni.id),
            ('status', '=', 'completed'),
        ])

        stats = {
            'permintaan_baru': len(requests_list),
            'sesi_aktif': sesi_aktif,
            'sesi_selesai': sesi_selesai,
            'rating': round(alumni.rating, 1) if alumni.rating else '0.0',
        }
        return request.render('mentorize.dashboard_alumni', {
            'user': user,
            'alumni': alumni,
            'requests': requests_list,
            'stats': stats,
        })
    
    @http.route(['/alumni/sesi', '/mentorize/alumni/sesi'], type='http', auth='user', website=True)
    def sesi_mentoring_alumni(self, **kwargs):
        user = request.env.user.sudo()
        alumni = self._ensure_alumni()

        Session = request.env['mentorize.session'].sudo()

        now = odoo_fields.Datetime.now()

        upcoming_sessions = Session.search([
            ('request_id.alumni_id', '=', alumni.id),
            ('status', 'in', ['scheduled', 'rescheduled']),
            ('tanggal_mentoring', '>=', now),
        ], order='tanggal_mentoring asc', limit=3)

        active_sessions = Session.search([
            ('request_id.alumni_id', '=', alumni.id),
            ('status', '=', 'scheduled'),
            ('tanggal_mentoring', '<=', now),
        ], order='tanggal_mentoring asc')

        history_sessions = Session.search([
            ('request_id.alumni_id', '=', alumni.id),
            ('status', 'in', ['completed', 'cancelled']),
        ], order='tanggal_mentoring desc')

        return request.render('mentorize.page_sesi_mentoring_alumni', {
            'user': user,
            'alumni': alumni,
            'upcoming_sessions': upcoming_sessions,
            'active_sessions': active_sessions,
            'history_sessions': history_sessions,
        })

    @http.route(['/alumni/request/<int:req_id>/approve', '/mentorize/alumni/request/<int:req_id>/approve'], type='http', auth='user', website=True)
    def approve_request(self, req_id, **kwargs):
        req = request.env['mentorize.request'].sudo().browse(req_id)
        if req.exists() and req.alumni_id.user_id.id == request.env.user.id:
            req.write({'status': 'approved'})
            if not req.room_chat_id:
                room = request.env['mentorize.roomchat'].sudo().create({'request_id': req.id})
                req.write({'room_chat_id': room.id})
        return request.redirect('/alumni/dashboard')

    @http.route(['/alumni/request/<int:req_id>/reject', '/mentorize/alumni/request/<int:req_id>/reject'], type='http', auth='user', website=True)
    def reject_request(self, req_id, **kwargs):
        req = request.env['mentorize.request'].sudo().browse(req_id)
        if req.exists() and req.alumni_id.user_id.id == request.env.user.id:
            req.write({'status': 'rejected'})
        return request.redirect('/alumni/dashboard')

    # =====================
    # ADMIN + PLACEHOLDER ROUTES
    # =====================
    @http.route(['/admin/dashboard', '/mentorize/admin/dashboard'], type='http', auth='user', website=True)
    def dashboard_admin(self, **kwargs):
        status = {
            'mahasiswa': request.env['mentorize.mahasiswa'].sudo().search_count([]),
            'alumni': request.env['mentorize.alumni'].sudo().search_count([]),
            'request': request.env['mentorize.request'].sudo().search_count([]),
            'session': request.env['mentorize.session'].sudo().search_count([]),
        }
        return request.render('mentorize.dashboard_admin', {
            'user': request.env.user.sudo(),
            'status': status,
        })

    @http.route('/sessions', type='http', auth='user', website=True)
    def sessions_redirect(self, **kwargs):
        role = self._current_role()

        if role == 'alumni':
            return request.redirect('/mentorize/alumni/sesi')

        if role == 'mahasiswa':
            return request.redirect('/mentorize/mahasiswa/sesi')

        return request.redirect('/mentorize/alumni/sesi')


    @http.route(['/chat', '/history', '/mentorize/mahasiswa/chat', '/mentorize/mahasiswa/riwayat', '/mentorize/mahasiswa/sessions'], type='http', auth='user', website=True)
    def coming_soon(self, **kwargs):
        return request.render('mentorize.page_coming_soon', {
            'user': request.env.user.sudo(),
        })
