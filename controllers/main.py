from odoo import http
from odoo import fields as odoo_fields
from odoo.http import request


class MentorizeController(http.Controller):

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
            return request.redirect('/mentorize/alumni/dashboard')
        if role == 'admin':
            return request.redirect('/mentorize/admin/dashboard')
        return request.redirect('/mentorize/mahasiswa/dashboard')

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
            try:
                user.sudo().write({'groups_id': [(4, request.env.ref(group_xmlid).id)]})
            except Exception:
                pass

    def _get_recommended_mentors(self, mahasiswa, limit=4):
        Alumni = request.env['mentorize.alumni'].sudo()
        alumni_pool = Alumni.search([('ketersediaan', '=', 'available')], limit=40)
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
    # PUBLIC ROUTES
    # =====================
    @http.route('/mentorize', type='http', auth='public', website=True)
    def index(self, **kwargs):
        return request.redirect('/mentorize/login')

    @http.route('/mentorize/login', type='http', auth='public', website=True)
    def login(self, **kwargs):
        return request.render('mentorize.page_login', {
            'error': self._login_error_message(kwargs.get('error')),
        })

    @http.route('/mentorize/login/submit', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def login_submit(self, **kwargs):
        email = (kwargs.get('email') or '').strip()
        password = kwargs.get('password') or ''
        role = kwargs.get('role') or 'mahasiswa'

        if not email or not password:
            return request.redirect('/mentorize/login?error=required')

        try:
            uid = request.session.authenticate(request.db, email, password)
        except Exception:
            uid = False

        if not uid:
            return request.redirect('/mentorize/login?error=1')

        user = request.env['res.users'].sudo().browse(uid)
        if user.mentorize_role and user.mentorize_role != role:
            request.session.logout(keep_db=True)
            return request.redirect('/mentorize/login?error=role')

        if role == 'alumni':
            return request.redirect('/mentorize/alumni/dashboard')
        return request.redirect('/mentorize/mahasiswa/dashboard')

    @http.route('/mentorize/forgot-password', type='http', auth='public', website=True)
    def forgot_password(self, **kwargs):
        return request.render('mentorize.page_forgot_password')

    @http.route('/mentorize/forgot-password/submit', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def forgot_password_submit(self, **kwargs):
        email = (kwargs.get('email') or '').strip()
        user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if not user:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Email tidak ditemukan.'
            })
        try:
            user.sudo().action_reset_password()
            return request.render('mentorize.page_forgot_password', {'success': True})
        except Exception:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Gagal mengirim email. Silakan coba lagi.'
            })

    @http.route('/mentorize/register', type='http', auth='public', website=True)
    def register(self, **kwargs):
        return request.render('mentorize.page_register')

    @http.route('/mentorize/register/submit', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def register_submit(self, **kwargs):
        name = (kwargs.get('name') or '').strip()
        email = (kwargs.get('email') or '').strip()
        password = kwargs.get('password') or ''
        confirm_password = kwargs.get('confirm_password') or ''
        role = kwargs.get('role') or 'mahasiswa'
        identity = (kwargs.get('identity') or '').strip()

        if password != confirm_password:
            return request.render('mentorize.page_register', {
                'error': 'Password dan konfirmasi password tidak sama!'
            })

        existing = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if existing:
            return request.render('mentorize.page_register', {
                'error': 'Email sudah terdaftar, silakan gunakan email lain.'
            })

        try:
            new_user = request.env['res.users'].sudo().with_context(no_reset_password=True).create({
                'name': name,
                'login': email,
                'email': email,
                'password': password,
                'mentorize_role': role,
            })
            new_user.sudo().write({'mentorize_role': role})
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
                if role == 'alumni':
                    return request.redirect('/mentorize/alumni/dashboard')
                else:
                    return request.redirect('/mentorize/mahasiswa/dashboard')
        except Exception as e:
            return request.render('mentorize.page_register', {
                'error': 'Terjadi kesalahan: ' + str(e)
            })
        return request.redirect('/mentorize/login')

    # =====================
    # MAHASISWA ROUTES
    # =====================
    @http.route(['/mentorize/mahasiswa/dashboard', '/dashboard', '/mentorize/dashboard'], type='http', auth='user', website=True)
    def dashboard_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/mentorize/alumni/dashboard')

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
            'total_request': request.env['mentorize.request'].sudo().search_count([
                ('mahasiswa_id', '=', mahasiswa.id)
            ]),
            'approved': request.env['mentorize.request'].sudo().search_count([
                ('mahasiswa_id', '=', mahasiswa.id), ('status', '=', 'approved')
            ]),
            'pending': request.env['mentorize.request'].sudo().search_count([
                ('mahasiswa_id', '=', mahasiswa.id), ('status', '=', 'pending')
            ]),
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
            'rekomendasi': rekomendasi,
            'stats': stats,
        })

    # =====================
    # PROFIL MAHASISWA
    # =====================
    @http.route(['/mentorize/mahasiswa/profil', '/profile', '/mentorize/profile'], type='http', auth='user', website=True)
    def profil_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/mentorize/alumni/dashboard')
        mahasiswa = self._ensure_mahasiswa()
        profil_lengkap = bool(
            mahasiswa.nim and mahasiswa.jurusan and
            mahasiswa.minat_ids and mahasiswa.skill_ids
        )
        return request.render('mentorize.page_profil_mahasiswa', {
            'user': request.env.user.sudo(),
            'mahasiswa': mahasiswa,
            'profil_lengkap': profil_lengkap,
            'success': kwargs.get('success'),
        })

    @http.route(['/mentorize/mahasiswa/profil/edit', '/profile/edit'], type='http', auth='user', website=True)
    def edit_profil_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/mentorize/alumni/dashboard')
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

    @http.route(['/mentorize/mahasiswa/profil/update', '/profile/update'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def update_profil_mahasiswa(self, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        user = request.env.user.sudo()
        try:
            semester = kwargs.get('semester') or '0'
            tujuan_karir = kwargs.get('tujuan_karir') or ''
            minat_ids = [int(x) for x in request.httprequest.form.getlist('minat_ids') if x]
            skill_ids = [int(x) for x in request.httprequest.form.getlist('skill_ids') if x]

            user.write({'name': kwargs.get('name') or user.name})
            mahasiswa.write({
                'nim': kwargs.get('nim') or mahasiswa.nim,
                'jurusan': kwargs.get('jurusan') or '',
                'semester': int(semester) if semester.isdigit() else 0,
                'tujuan_karir': tujuan_karir,
                'minat_ids': [(6, 0, minat_ids)],
                'skill_ids': [(6, 0, skill_ids)],
            })
            return request.redirect('/mentorize/mahasiswa/profil?success=1')
        except Exception as e:
            return request.render('mentorize.page_edit_profil_mahasiswa', {
                'user': user,
                'mahasiswa': mahasiswa,
                'all_minat': request.env['mentorize.minat'].sudo().search([], order='name asc'),
                'all_skill': request.env['mentorize.skill'].sudo().search([], order='name asc'),
                'selected_minat_ids': mahasiswa.minat_ids.ids,
                'selected_skill_ids': mahasiswa.skill_ids.ids,
                'error': 'Terjadi kesalahan: ' + str(e),
            })

    # =====================
    # LIST MENTOR
    # =====================
    @http.route(['/mentorize/mentor', '/mentor', '/mentors', '/mentorize/mahasiswa/cari-mentor'], type='http', auth='user', website=True)
    def list_mentor(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if mahasiswa:
            request.env['mentorize.matchmaking'].sudo().generate_matchmaking(mahasiswa.id)

        alumni_list = request.env['mentorize.alumni'].sudo().search([
            ('ketersediaan', '=', 'available'),
        ])

        matchmaking_data = {}
        if mahasiswa:
            matchmakings = request.env['mentorize.matchmaking'].sudo().search([
                ('mahasiswa_id', '=', mahasiswa.id)
            ])
            for m in matchmakings:
                matchmaking_data[m.alumni_id.id] = {
                    'score': m.score,
                    'is_recommended': m.is_recommended,
                    'skill_match': m.skill_match,
                }

        skills = request.env['mentorize.skill'].sudo().search([])

        return request.render('mentorize.page_list_mentor', {
            'alumni_list': alumni_list,
            'matchmaking_data': matchmaking_data,
            'mahasiswa': mahasiswa,
            'skills': skills,
            'user': request.env.user.sudo(),
        })

    # =====================
    # DETAIL MENTOR
    # =====================
    @http.route(['/mentorize/mentor/<int:alumni_id>', '/mentors/<int:alumni_id>'], type='http', auth='user', website=True)
    def detail_mentor(self, alumni_id, **kwargs):
        user = request.env.user
        alumni = request.env['mentorize.alumni'].sudo().browse(alumni_id)

        if not alumni.exists():
            return request.redirect('/mentorize/mentor')

        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        existing_request = False
        if mahasiswa:
            existing_request = request.env['mentorize.request'].sudo().search([
                ('mahasiswa_id', '=', mahasiswa.id),
                ('alumni_id', '=', alumni_id),
                ('status', 'in', ['pending', 'approved']),
            ], limit=1)

        match_info = None
        if mahasiswa:
            match_info = request.env['mentorize.matchmaking'].sudo().search([
                ('mahasiswa_id', '=', mahasiswa.id),
                ('alumni_id', '=', alumni_id),
            ], limit=1)

        feedbacks = request.env['mentorize.feedback'].sudo().search([
            ('alumni_id', '=', alumni_id)
        ], limit=5)

        return request.render('mentorize.page_detail_mentor', {
            'alumni': alumni,
            'mahasiswa': mahasiswa,
            'existing_request': existing_request,
            'match_info': match_info,
            'feedbacks': feedbacks,
            'user': request.env.user.sudo(),
        })

    # =====================
    # REQUEST MENTORING
    # =====================
    @http.route(['/mentors/<int:alumni_id>/request'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def request_mentor_alias(self, alumni_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        alumni = request.env['mentorize.alumni'].sudo().browse(alumni_id)
        if not alumni.exists():
            return request.redirect('/mentorize/mentor')
        existing = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('alumni_id', '=', alumni_id),
            ('status', 'in', ['pending', 'approved']),
        ], limit=1)
        if not existing:
            request.env['mentorize.request'].sudo().create({
                'mahasiswa_id': mahasiswa.id,
                'alumni_id': alumni_id,
                'topik': kwargs.get('topik') or 'Mentoring karier dan pengembangan skill',
                'deskripsi': kwargs.get('deskripsi') or '',
                'status': 'pending',
            })
        return request.redirect('/mentorize/mahasiswa/riwayat?success=1')

    # =====================
    # RIWAYAT & STATUS
    # =====================
    @http.route(['/mentorize/mahasiswa/riwayat', '/history', '/riwayat', '/mentorize/history'], type='http', auth='user', website=True)
    def riwayat_mahasiswa(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        requests = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id)
        ], order='tanggal_request desc')

        success = kwargs.get('success', False)

        return request.render('mentorize.page_riwayat_mahasiswa', {
            'mahasiswa': mahasiswa,
            'requests': requests,
            'success': success,
            'user': request.env.user.sudo(),
        })

    # =====================
    # REKOMENDASI MENTOR
    # =====================
    @http.route(['/mentorize/mentor/rekomendasi', '/mentorize/recommendations', '/recommendations'], type='http', auth='user', website=True)
    def rekomendasi_mentor(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        request.env['mentorize.matchmaking'].sudo().generate_matchmaking(mahasiswa.id)

        matchmakings = request.env['mentorize.matchmaking'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
        ], order='score desc', limit=10)

        return request.render('mentorize.page_rekomendasi_mentor', {
            'mahasiswa': mahasiswa,
            'matchmakings': matchmakings,
            'user': request.env.user.sudo(), 
        })

    # =====================
    # SESI MENTORING MAHASISWA
    # =====================
    @http.route('/mentorize/mahasiswa/sesi', type='http', auth='user', website=True)
    def sesi_mentoring_mahasiswa(self, **kwargs):
        if self._current_role() == 'alumni':
            return request.redirect('/mentorize/alumni/sesi')

        user = request.env.user.sudo()
        mahasiswa = self._ensure_mahasiswa()
        Session = request.env['mentorize.session'].sudo()
        RequestMentoring = request.env['mentorize.request'].sudo()
        now = odoo_fields.Datetime.now()

        approved_requests = RequestMentoring.search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'approved'),
        ], order='tanggal_request desc')

        upcoming_sessions = Session.search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', 'in', ['scheduled', 'rescheduled']),
            ('tanggal_mentoring', '>=', now),
        ], order='tanggal_mentoring asc')

        active_sessions = Session.search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'scheduled'),
            ('tanggal_mentoring', '<=', now),
        ], order='tanggal_mentoring asc')

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

    @http.route('/mentorize/mahasiswa/sesi/ajukan', type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def ajukan_jadwal_mahasiswa(self, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        req_id = int(kwargs.get('request_id') or 0)
        req = request.env['mentorize.request'].sudo().browse(req_id)

        if not req.exists() or req.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/mentorize/mahasiswa/sesi')

        tanggal = (kwargs.get('tanggal_mentoring') or '').replace('T', ' ')

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

    @http.route('/mentorize/session/<int:session_id>/cancel', type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def cancel_session_mahasiswa(self, session_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        sesi = request.env['mentorize.session'].sudo().browse(session_id)
        if sesi.exists() and sesi.request_id.mahasiswa_id.id == mahasiswa.id:
            sesi.write({'status': 'cancelled'})
        return request.redirect('/mentorize/mahasiswa/sesi')

    @http.route('/mentorize/session/<int:session_id>/reschedule', type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def reschedule_session_mahasiswa(self, session_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        sesi = request.env['mentorize.session'].sudo().browse(session_id)
        if sesi.exists() and sesi.request_id.mahasiswa_id.id == mahasiswa.id:
            tanggal = (kwargs.get('tanggal_mentoring') or '').replace('T', ' ')
            sesi.write({
                'tanggal_mentoring': tanggal,
                'ringkasan_materi': kwargs.get('ringkasan_materi') or sesi.ringkasan_materi,
                'status': 'rescheduled',
            })
        return request.redirect('/mentorize/mahasiswa/sesi')

    @http.route('/mentorize/session/<int:session_id>/complete', type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def complete_session_mahasiswa(self, session_id, **kwargs):
        mahasiswa = self._ensure_mahasiswa()
        sesi = request.env['mentorize.session'].sudo().browse(session_id)
        if sesi.exists() and sesi.request_id.mahasiswa_id.id == mahasiswa.id:
            sesi.write({'status': 'completed'})
        return request.redirect('/mentorize/mahasiswa/sesi')

    # =====================
    # ALUMNI ROUTES
    # =====================
    @http.route(['/mentorize/alumni/dashboard', '/alumni/dashboard'], type='http', auth='user', website=True)
    def dashboard_alumni(self, **kwargs):
        user = request.env.user.sudo()
        alumni = self._ensure_alumni()

        pending_requests = request.env['mentorize.request'].sudo().search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'pending'),
        ], order='tanggal_request desc')

        stats = {
            'permintaan_baru': len(pending_requests),
            'sesi_aktif': request.env['mentorize.session'].sudo().search_count([
                ('request_id.alumni_id', '=', alumni.id),
                ('status', '=', 'scheduled'),
            ]),
            'sesi_selesai': request.env['mentorize.session'].sudo().search_count([
                ('request_id.alumni_id', '=', alumni.id),
                ('status', '=', 'completed'),
            ]),
            'rating': round(alumni.rating, 1) if alumni.rating else 0.0,
        }

        return request.render('mentorize.dashboard_alumni', {
            'user': user,
            'alumni': alumni,
            'pending_requests': pending_requests,
            'requests': pending_requests,
            'stats': stats,
        })

    @http.route(['/mentorize/alumni/sesi', '/sessions', '/mentorize/sessions'], type='http', auth='user', website=True)
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

    @http.route('/mentorize/alumni/request/<int:req_id>/approve', type='http', auth='user', website=True)
    def approve_request(self, req_id, **kwargs):
        req = request.env['mentorize.request'].sudo().browse(req_id)
        if req.exists():
            req.write({'status': 'approved'})
            req.alumni_id.sudo().write({
                'slot_mentoring': max(0, req.alumni_id.slot_mentoring - 1)
            })
            if not req.room_chat_id:
                room = request.env['mentorize.roomchat'].sudo().create({'request_id': req.id})
                req.write({'room_chat_id': room.id})
        return request.redirect('/mentorize/alumni/dashboard')

    @http.route('/mentorize/alumni/request/<int:req_id>/reject', type='http', auth='user', website=True)
    def reject_request(self, req_id, **kwargs):
        req = request.env['mentorize.request'].sudo().browse(req_id)
        if req.exists():
            req.write({'status': 'rejected'})
        return request.redirect('/mentorize/alumni/dashboard')

    @http.route('/mentorize/alumni/riwayat', type='http', auth='user', website=True)
    def riwayat_alumni(self, **kwargs):
        user = request.env.user
        alumni = request.env['mentorize.alumni'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not alumni:
            return request.redirect('/mentorize/login')

        all_requests = request.env['mentorize.request'].sudo().search([
            ('alumni_id', '=', alumni.id)
        ], order='tanggal_request desc')

        return request.render('mentorize.page_riwayat_alumni', {
            'alumni': alumni,
            'requests': all_requests,
            'user': request.env.user.sudo(),
        })

    @http.route('/mentorize/alumni/requests', type='http', auth='user', website=True)
    def alumni_requests(self, **kwargs):
        user = request.env.user
        alumni = request.env['mentorize.alumni'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        if not alumni:
            return request.redirect('/mentorize/login')
        pending_requests = request.env['mentorize.request'].sudo().search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'pending')
        ], order='tanggal_request desc')
        all_requests = request.env['mentorize.request'].sudo().search([
            ('alumni_id', '=', alumni.id)
        ], order='tanggal_request desc')
        return request.render('mentorize.page_riwayat_alumni', {
            'alumni': alumni,
            'requests': all_requests,
            'pending_requests': pending_requests,
            'user': request.env.user.sudo(),
        })
    
    @http.route(['/chat', '/mentorize/chat', '/mentorize/mahasiswa/chat', '/mentorize/chat/request/<int:req_id>'], type='http', auth='user', website=True)
    def chat_coming_soon(self, req_id=None, **kwargs):
        return request.render('mentorize.page_coming_soon', {
        'user': request.env.user.sudo(),
        'req_id': req_id,
    })

    # =====================
    # ADMIN ROUTES
    # =====================
    @http.route('/mentorize/admin/dashboard', type='http', auth='user', website=True)
    def dashboard_admin(self, **kwargs):
        user = request.env.user
        return request.render('mentorize.dashboard_admin', {
            'user': user,
        })