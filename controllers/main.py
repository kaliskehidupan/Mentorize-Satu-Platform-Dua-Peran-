from odoo import http
from odoo.http import request

class MentorizeController(http.Controller):

    # =====================
    # PUBLIC ROUTES
    # =====================
    @http.route('/mentorize', type='http', auth='public', website=True)
    def index(self, **kwargs):
        return request.redirect('/mentorize/login')

    @http.route('/mentorize/login', type='http', auth='public', website=True)
    def login(self, **kwargs):
        return request.render('mentorize.page_login')

    @http.route('/mentorize/login/submit', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def login_submit(self, **kwargs):
        email = kwargs.get('email')
        password = kwargs.get('password')
        role = kwargs.get('role', 'mahasiswa')
        try:
            uid = request.session.authenticate(request.db, email, password)
            if uid:
                if role == 'alumni':
                    return request.redirect('/mentorize/alumni/dashboard')
                else:
                    return request.redirect('/mentorize/mahasiswa/dashboard')
        except Exception:
            pass
        return request.redirect('/mentorize/login?error=1')

    @http.route('/mentorize/forgot-password', type='http', auth='public', website=True)
    def forgot_password(self, **kwargs):
        return request.render('mentorize.page_forgot_password')

    @http.route('/mentorize/register', type='http', auth='public', website=True)
    def register(self, **kwargs):
        return request.render('mentorize.page_register')

    @http.route('/mentorize/register/submit', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def register_submit(self, **kwargs):
        name = kwargs.get('name', '').strip()
        email = kwargs.get('email', '').strip()
        password = kwargs.get('password', '')
        confirm_password = kwargs.get('confirm_password', '')
        role = kwargs.get('role', 'mahasiswa')
        identity = kwargs.get('identity', '').strip()

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
            new_user = request.env['res.users'].sudo().create({
                'name': name,
                'login': email,
                'email': email,
                'password': password,
                'mentorize_role': role,
            })

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

    @http.route('/mentorize/forgot-password/submit', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def forgot_password_submit(self, **kwargs):
        email = kwargs.get('email', '').strip()
        user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)

        if not user:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Email tidak ditemukan.'
            })

        try:
            user.sudo().action_reset_password()
            return request.render('mentorize.page_forgot_password', {
                'success': True
            })
        except Exception:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Gagal mengirim email. Silakan coba lagi.'
            })

    # =====================
    # MAHASISWA ROUTES
    # =====================
    @http.route('/mentorize/mahasiswa/dashboard', type='http', auth='user', website=True)
    def dashboard_mahasiswa(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        # Ambil request terbaru
        requests = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id)
        ], order='tanggal_request desc', limit=5)

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
        }

        return request.render('mentorize.dashboard_mahasiswa', {
            'user': user,
            'mahasiswa': mahasiswa,
            'requests': requests,
            'stats': stats,
        })

    # =====================
    # LIST MENTOR
    # =====================
    @http.route('/mentorize/mentor', type='http', auth='user', website=True)
    def list_mentor(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        # Generate matchmaking otomatis
        if mahasiswa:
            request.env['mentorize.matchmaking'].sudo().generate_matchmaking(mahasiswa.id)

        # Ambil semua alumni available
        alumni_list = request.env['mentorize.alumni'].sudo().search([
            ('ketersediaan', '=', 'available'),
        ])

        # Ambil matchmaking score untuk sorting
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

        # Ambil semua skill untuk filter
        skills = request.env['mentorize.skill'].sudo().search([])

        return request.render('mentorize.page_list_mentor', {
            'alumni_list': alumni_list,
            'matchmaking_data': matchmaking_data,
            'mahasiswa': mahasiswa,
            'skills': skills,
        })

    # =====================
    # DETAIL MENTOR
    # =====================
    @http.route('/mentorize/mentor/<int:alumni_id>', type='http', auth='user', website=True)
    def detail_mentor(self, alumni_id, **kwargs):
        user = request.env.user
        alumni = request.env['mentorize.alumni'].sudo().browse(alumni_id)

        if not alumni.exists():
            return request.redirect('/mentorize/mentor')

        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        # Cek apakah sudah pernah request ke mentor ini
        existing_request = False
        if mahasiswa:
            existing_request = request.env['mentorize.request'].sudo().search([
                ('mahasiswa_id', '=', mahasiswa.id),
                ('alumni_id', '=', alumni_id),
                ('status', 'in', ['pending', 'approved']),
            ], limit=1)

        # Ambil matchmaking score
        match_info = None
        if mahasiswa:
            match_info = request.env['mentorize.matchmaking'].sudo().search([
                ('mahasiswa_id', '=', mahasiswa.id),
                ('alumni_id', '=', alumni_id),
            ], limit=1)

        # Ambil feedback/review
        feedbacks = request.env['mentorize.feedback'].sudo().search([
            ('alumni_id', '=', alumni_id)
        ], limit=5)

        return request.render('mentorize.page_detail_mentor', {
            'alumni': alumni,
            'mahasiswa': mahasiswa,
            'existing_request': existing_request,
            'match_info': match_info,
            'feedbacks': feedbacks,
        })

    # =====================
    # REQUEST MENTORING
    # =====================
    @http.route('/mentorize/mentor/request/<int:alumni_id>', type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def submit_request(self, alumni_id, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        alumni = request.env['mentorize.alumni'].sudo().browse(alumni_id)
        if not alumni.exists():
            return request.redirect('/mentorize/mentor')

        # Cek request duplikat
        existing = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('alumni_id', '=', alumni_id),
            ('status', 'in', ['pending', 'approved']),
        ], limit=1)

        if existing:
            return request.redirect('/mentorize/mentor/' + str(alumni_id) + '?error=duplicate')

        topik = kwargs.get('topik', '').strip()
        deskripsi = kwargs.get('deskripsi', '').strip()

        if not topik:
            return request.redirect('/mentorize/mentor/' + str(alumni_id) + '?error=notopic')

        try:
            request.env['mentorize.request'].sudo().create({
                'mahasiswa_id': mahasiswa.id,
                'alumni_id': alumni_id,
                'topik': topik,
                'deskripsi': deskripsi,
                'status': 'pending',
            })
        except Exception as e:
            return request.redirect('/mentorize/mentor/' + str(alumni_id) + '?error=failed')

        return request.redirect('/mentorize/mahasiswa/riwayat?success=1')

    # =====================
    # RIWAYAT & STATUS
    # =====================
    @http.route('/mentorize/mahasiswa/riwayat', type='http', auth='user', website=True)
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
        })

    # =====================
    # REKOMENDASI MENTOR
    # =====================
    @http.route('/mentorize/mentor/rekomendasi', type='http', auth='user', website=True)
    def rekomendasi_mentor(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        # Generate ulang matchmaking
        request.env['mentorize.matchmaking'].sudo().generate_matchmaking(mahasiswa.id)

        # Ambil top rekomendasi
        matchmakings = request.env['mentorize.matchmaking'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
        ], order='score desc', limit=10)

        return request.render('mentorize.page_rekomendasi_mentor', {
            'mahasiswa': mahasiswa,
            'matchmakings': matchmakings,
        })

    # =====================
    # ALUMNI ROUTES
    # =====================
    @http.route('/mentorize/alumni/dashboard', type='http', auth='user', website=True)
    def dashboard_alumni(self, **kwargs):
        user = request.env.user
        alumni = request.env['mentorize.alumni'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not alumni:
            return request.redirect('/mentorize/login')

        # Ambil request pending
        pending_requests = request.env['mentorize.request'].sudo().search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'pending')
        ], order='tanggal_request desc')

        stats = {
            'permintaan_baru': len(pending_requests),
            'sesi_aktif': request.env['mentorize.session'].sudo().search_count([
                ('request_id.alumni_id', '=', alumni.id),
                ('status', '=', 'scheduled')
            ]),
            'sesi_selesai': request.env['mentorize.session'].sudo().search_count([
                ('request_id.alumni_id', '=', alumni.id),
                ('status', '=', 'completed')
            ]),
            'rating': round(alumni.rating, 1) if alumni.rating else 0.0,
        }

        return request.render('mentorize.dashboard_alumni', {
            'user': user,
            'alumni': alumni,
            'pending_requests': pending_requests,
            'stats': stats,
        })

    @http.route('/mentorize/alumni/request/<int:req_id>/approve', type='http', auth='user', website=True)
    def approve_request(self, req_id, **kwargs):
        req = request.env['mentorize.request'].sudo().browse(req_id)
        if req.exists():
            req.write({'status': 'approved'})
            # Kurangi slot mentoring alumni
            req.alumni_id.sudo().write({
                'slot_mentoring': max(0, req.alumni_id.slot_mentoring - 1)
            })
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
        })

    # =====================
    # ADMIN ROUTES
    # =====================
    @http.route('/mentorize/admin/dashboard', type='http', auth='user', website=True)
    def dashboard_admin(self, **kwargs):
        return request.render('mentorize.dashboard_admin')
