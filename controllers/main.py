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

    # ✅ TAMBAHKAN INI — tepat di sini
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

        # cari user dengan email tersebut
        user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)

        if not user:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Email tidak ditemukan. Pastikan email yang Anda masukkan sudah benar.'
            })

        try:
            # gunakan fitur reset password bawaan Odoo
            user.sudo().action_reset_password()
            return request.render('mentorize.page_forgot_password', {
                'success': True
            })
        except Exception as e:
            return request.render('mentorize.page_forgot_password', {
                'error': 'Gagal mengirim email. Silakan coba lagi.'
            })
            
        @http.route('/mentorize/alumni/dashboard', type='http', auth='user', website=True)
        def dashboard_alumni(self, **kwargs):
            user = request.env.user
            alumni = request.env['mentorize.alumni'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)

            if not alumni:
                return request.redirect('/mentorize/login')

            # ambil request pending
            requests = request.env['mentorize.request'].sudo().search([
                ('alumni_id', '=', alumni.id),
                ('status', '=', 'pending')
            ], order='tanggal_request desc', limit=10)

            # hitung stats
            sesi_aktif = request.env['mentorize.session'].sudo().search_count([
                ('request_id.alumni_id', '=', alumni.id),
                ('status', '=', 'scheduled')
            ])
            sesi_selesai = request.env['mentorize.session'].sudo().search_count([
                ('request_id.alumni_id', '=', alumni.id),
                ('status', '=', 'completed')
            ])

            stats = {
                'permintaan_baru': len(requests),
                'sesi_aktif': sesi_aktif,
                'sesi_selesai': sesi_selesai,
                'rating': round(alumni.rating, 1) if alumni.rating else '0.0',
            }

            return request.render('mentorize.dashboard_alumni', {
                'user': user,
                'alumni': alumni,
                'requests': requests,
                'stats': stats,
            })

        @http.route('/mentorize/alumni/request/<int:req_id>/approve', type='http', auth='user', website=True)
        def approve_request(self, req_id, **kwargs):
            req = request.env['mentorize.request'].sudo().browse(req_id)
            if req.exists():
                req.write({'status': 'approved'})
            return request.redirect('/mentorize/alumni/dashboard')

        @http.route('/mentorize/alumni/request/<int:req_id>/reject', type='http', auth='user', website=True)
        def reject_request(self, req_id, **kwargs):
            req = request.env['mentorize.request'].sudo().browse(req_id)
            if req.exists():
                req.write({'status': 'rejected'})
            return request.redirect('/mentorize/alumni/dashboard')


    # =====================
    # MAHASISWA ROUTES
    # =====================
    @http.route('/mentorize/mahasiswa/dashboard', type='http', auth='user', website=True)
    def dashboard_mahasiswa(self, **kwargs):
        return request.render('mentorize.dashboard_mahasiswa')

    # =====================
    # ALUMNI ROUTES
    # =====================
    @http.route('/mentorize/alumni/dashboard', type='http', auth='user', website=True)
    def dashboard_alumni(self, **kwargs):
        return request.render('mentorize.dashboard_alumni')

    # =====================
    # ADMIN ROUTES
    # =====================
    @http.route('/mentorize/admin/dashboard', type='http', auth='user', website=True)
    def dashboard_admin(self, **kwargs):
        return request.render('mentorize.dashboard_admin')