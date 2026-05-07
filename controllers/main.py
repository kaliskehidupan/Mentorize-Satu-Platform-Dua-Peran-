from odoo import http
from odoo.http import request

class MentorizeController(http.Controller):

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
            mahasiswa = request.env['mentorize.mahasiswa'].sudo().create({
                'user_id': user.id,
                'nim': user.nim or '',
                'jurusan': user.jurusan or '',
            })

        mentoring_aktif = request.env['mentorize.request'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'approved')
        ])

        jadwal_terdekat = request.env['mentorize.session'].sudo().search([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'scheduled')
        ], order='tanggal_mentoring asc', limit=5)

        sesi_berjalan = request.env['mentorize.session'].sudo().search_count([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'scheduled')
        ])
        sesi_selesai = request.env['mentorize.session'].sudo().search_count([
            ('request_id.mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'completed')
        ])
        total_sesi = sesi_berjalan + sesi_selesai
        progress_pct = round((sesi_selesai / total_sesi * 100)) if total_sesi > 0 else 0

        stats = {
            'mentor_aktif': len(mentoring_aktif),
            'sesi_berjalan': sesi_berjalan,
            'sesi_selesai': sesi_selesai,
            'progress_pct': progress_pct,
        }

        return request.render('mentorize.dashboard_mahasiswa', {
            'user': user,
            'mahasiswa': mahasiswa,
            'mentoring_aktif': mentoring_aktif,
            'jadwal_terdekat': jadwal_terdekat,
            'stats': stats,
        })

    # =====================
    # PROFIL MAHASISWA
    # =====================
    @http.route('/mentorize/mahasiswa/profil', type='http', auth='user', website=True)
    def profil_mahasiswa(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        profil_lengkap = bool(
            mahasiswa.nim and
            mahasiswa.jurusan and
            user.tujuan_karir and
            mahasiswa.minat_ids and
            mahasiswa.skill_ids
        )

        return request.render('mentorize.page_profil_mahasiswa', {
            'user': user,
            'mahasiswa': mahasiswa,
            'profil_lengkap': profil_lengkap,
        })

    @http.route('/mentorize/mahasiswa/profil/edit', type='http', auth='user', website=True)
    def edit_profil_mahasiswa(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        all_minat = request.env['mentorize.minat'].sudo().search([])
        all_skill = request.env['mentorize.skill'].sudo().search([])

        return request.render('mentorize.page_edit_profil_mahasiswa', {
            'user': user,
            'mahasiswa': mahasiswa,
            'all_minat': all_minat,
            'all_skill': all_skill,
            'selected_minat_ids': mahasiswa.minat_ids.ids,
            'selected_skill_ids': mahasiswa.skill_ids.ids,
        })

    @http.route('/mentorize/mahasiswa/profil/update', type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def update_profil_mahasiswa(self, **kwargs):
        user = request.env.user
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)

        if not mahasiswa:
            return request.redirect('/mentorize/login')

        try:
            user.sudo().write({
                'name': kwargs.get('name', user.name),
                'tujuan_karir': kwargs.get('tujuan_karir', ''),
            })

            semester = kwargs.get('semester', '')
            mahasiswa.sudo().write({
                'nim': kwargs.get('nim', ''),
                'jurusan': kwargs.get('jurusan', ''),
                'semester': int(semester) if semester else 0,
            })

            minat_ids = request.httprequest.form.getlist('minat_ids')
            if minat_ids:
                mahasiswa.sudo().write({
                    'minat_ids': [(6, 0, [int(x) for x in minat_ids])]
                })

            skill_ids = request.httprequest.form.getlist('skill_ids')
            if skill_ids:
                mahasiswa.sudo().write({
                    'skill_ids': [(6, 0, [int(x) for x in skill_ids])]
                })

            return request.redirect('/mentorize/mahasiswa/profil?success=1')

        except Exception as e:
            all_minat = request.env['mentorize.minat'].sudo().search([])
            all_skill = request.env['mentorize.skill'].sudo().search([])
            return request.render('mentorize.page_edit_profil_mahasiswa', {
                'user': user,
                'mahasiswa': mahasiswa,
                'all_minat': all_minat,
                'all_skill': all_skill,
                'selected_minat_ids': mahasiswa.minat_ids.ids,
                'selected_skill_ids': mahasiswa.skill_ids.ids,
                'error': 'Terjadi kesalahan: ' + str(e),
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

        requests_list = request.env['mentorize.request'].sudo().search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'pending')
        ], order='tanggal_request desc', limit=10)

        sesi_aktif = request.env['mentorize.session'].sudo().search_count([
            ('request_id.alumni_id', '=', alumni.id),
            ('status', '=', 'scheduled')
        ])
        sesi_selesai = request.env['mentorize.session'].sudo().search_count([
            ('request_id.alumni_id', '=', alumni.id),
            ('status', '=', 'completed')
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
    # ADMIN ROUTES
    # =====================
    @http.route('/mentorize/admin/dashboard', type='http', auth='user', website=True)
    def dashboard_admin(self, **kwargs):
        user = request.env.user
        return request.render('mentorize.dashboard_admin', {
            'user': user,
        })