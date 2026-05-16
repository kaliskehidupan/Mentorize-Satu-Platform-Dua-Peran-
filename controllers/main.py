import base64
import json
from datetime import datetime, timedelta

from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import AccessDenied


class MentorizeController(http.Controller):
    # ---------- helpers ----------
    def _json(self, payload, status=200):
        return Response(
            json.dumps(payload, default=str),
            status=status,
            content_type='application/json; charset=utf-8'
        )

    def _current_mahasiswa(self):
        user = request.env.user
        return request.env['mentorize.mahasiswa'].sudo().search([('user_id', '=', user.id)], limit=1)

    def _current_alumni(self):
        user = request.env.user
        return request.env['mentorize.alumni'].sudo().search([('user_id', '=', user.id)], limit=1)

    def _infer_user_role(self, user=None, selected_role=None):
        """Menentukan role Mentorize dengan aman, termasuk untuk akun lama.
        Prioritas: field mentorize_role -> grup -> data profil -> field nim/kapa -> role yang dipilih saat login.
        """
        user = user or request.env.user
        role = user.mentorize_role

        if role in ['mahasiswa', 'alumni', 'admin']:
            return role

        try:
            admin_group = request.env.ref('mentorize.group_mentorize_admin', raise_if_not_found=False)
            alumni_group = request.env.ref('mentorize.group_mentorize_alumni', raise_if_not_found=False)
            mahasiswa_group = request.env.ref('mentorize.group_mentorize_mahasiswa', raise_if_not_found=False)

            groups = user.sudo().groups_id

            if admin_group and admin_group in groups:
                return 'admin'
            if alumni_group and alumni_group in groups:
                return 'alumni'
            if mahasiswa_group and mahasiswa_group in groups:
                return 'mahasiswa'
        except Exception:
            pass

        Alumni = request.env['mentorize.alumni'].sudo()
        Mahasiswa = request.env['mentorize.mahasiswa'].sudo()

        if Alumni.search([('user_id', '=', user.id)], limit=1) or user.kapa:
            return 'alumni'
        if Mahasiswa.search([('user_id', '=', user.id)], limit=1) or user.nim:
            return 'mahasiswa'

        if selected_role in ['mahasiswa', 'alumni']:
            return selected_role

        return 'mahasiswa'

    def _sync_user_role(self, user=None, role=None):
        """Sinkronisasi role Mentorize + group Odoo.

        Penting:
        - Mahasiswa/Alumni wajib punya base.group_portal.
        - Tanpa Portal, user bisa bikin error saat akses website/login.
        - Group role Mentorize tetap ditambahkan sesuai role.
        """
        user = user or request.env.user
        role = role or self._infer_user_role(user)

        vals = {}
        commands = []

        if role and user.mentorize_role != role:
            vals['mentorize_role'] = role

        try:
            portal_group = request.env.ref('base.group_portal', raise_if_not_found=False)
            internal_group = request.env.ref('base.group_user', raise_if_not_found=False)

            mahasiswa_group = request.env.ref('mentorize.group_mentorize_mahasiswa', raise_if_not_found=False)
            alumni_group = request.env.ref('mentorize.group_mentorize_alumni', raise_if_not_found=False)
            admin_group = request.env.ref('mentorize.group_mentorize_admin', raise_if_not_found=False)

            current_groups = user.sudo().groups_id

            if role in ['mahasiswa', 'alumni']:
                # Mahasiswa/Alumni harus Portal, bukan user tanpa tipe.
                if portal_group and portal_group not in current_groups:
                    commands.append((4, portal_group.id))

                # Kalau ada internal group nyangkut di akun mahasiswa/alumni, lepaskan.
                # Ini menjaga tipe user tidak bentrok.
                if internal_group and internal_group in current_groups:
                    commands.append((3, internal_group.id))

                if role == 'mahasiswa':
                    if mahasiswa_group and mahasiswa_group not in current_groups:
                        commands.append((4, mahasiswa_group.id))
                    if alumni_group and alumni_group in current_groups:
                        commands.append((3, alumni_group.id))

                elif role == 'alumni':
                    if alumni_group and alumni_group not in current_groups:
                        commands.append((4, alumni_group.id))
                    if mahasiswa_group and mahasiswa_group in current_groups:
                        commands.append((3, mahasiswa_group.id))

            elif role == 'admin':
                if admin_group and admin_group not in current_groups:
                    commands.append((4, admin_group.id))

        except Exception:
            pass

        if commands:
            vals['groups_id'] = commands

        if vals:
            user.sudo().write(vals)

        return role

    def _ensure_profile(self, role=None):
        user = request.env.user
        role = role or self._infer_user_role(user)

        if role == 'mahasiswa':
            mahasiswa = self._current_mahasiswa()
            if not mahasiswa:
                mahasiswa = request.env['mentorize.mahasiswa'].sudo().create({
                    'user_id': user.id,
                    'nim': user.nim or '',
                    'jurusan': user.jurusan or '',
                    'tujuan_karir': user.tujuan_karir or '',
                    'bio': user.bio or '',
                })
            return mahasiswa

        if role == 'alumni':
            alumni = self._current_alumni()
            if not alumni:
                alumni = request.env['mentorize.alumni'].sudo().create({
                    'user_id': user.id,
                    'kapa': user.kapa or '',
                })
            return alumni

        return False

    def _redirect_after_login(self):
        user = request.env.user
        role = self._sync_user_role(user)

        if role == 'alumni':
            alumni = self._ensure_profile('alumni')
            if alumni and not alumni.profile_complete:
                return request.redirect('/alumni/profile/setup')
            return request.redirect('/alumni/dashboard')

        if role == 'admin':
            return request.redirect('/admin/dashboard')

        mahasiswa = self._ensure_profile('mahasiswa')
        if mahasiswa and not mahasiswa.profile_complete:
            return request.redirect('/profile/setup')

        return request.redirect('/dashboard')

    def _get_notifications(self, limit=8):
        if request.env.user._is_public():
            return request.env['mentorize.notification'].sudo().browse([])
        return request.env['mentorize.notification'].sudo().search(
            [('user_id', '=', request.env.user.id)],
            limit=limit
        )

    def _unread_count(self):
        if request.env.user._is_public():
            return 0
        return request.env['mentorize.notification'].sudo().search_count([
            ('user_id', '=', request.env.user.id),
            ('is_read', '=', False)
        ])

    def _layout_values(self, active='dashboard'):
        role = self._infer_user_role(request.env.user) if not request.env.user._is_public() else False
        return {
            'user': request.env.user,
            'role': role,
            'active_menu': active,
            'notifications': self._get_notifications(),
            'unread_count': self._unread_count(),
        }

    def _verify_mahasiswa_identity(self, nim, name):
        """Hook untuk integrasi API NIM asli nanti. Saat ini sengaja dibuat lolos dulu."""
        return True, 'OK'

    def _verify_alumni_identity(self, kapa, name):
        """Hook untuk integrasi API KAPA asli nanti. Saat ini sengaja dibuat lolos dulu."""
        return True, 'OK'

    def _recommend_mentors(self, mahasiswa, limit=6):
        Alumni = request.env['mentorize.alumni'].sudo()
        mentors = Alumni.search([('user_id', '!=', False), ('availability', '!=', 'offline')])

        scored = []
        mahasiswa_minat = set(mahasiswa.minat_ids.ids)
        mahasiswa_skill = set(mahasiswa.skill_ids.ids)

        for mentor in mentors:
            minat_match = len(mahasiswa_minat.intersection(set(mentor.minat_ids.ids)))
            skill_match = len(mahasiswa_skill.intersection(set(mentor.skill_ids.ids)))
            score = (minat_match * 20) + (skill_match * 25) + (10 if mentor.availability == 'available' else 0)

            if score > 0:
                scored.append((score, mentor))

        scored.sort(key=lambda item: item[0], reverse=True)

        if scored:
            return [mentor for score, mentor in scored[:limit]]

        return Alumni.search([('user_id', '!=', False), ('availability', '!=', 'offline')], limit=limit)

    def _room_allowed(self, room):
        user = request.env.user
        return room and (
            room.mahasiswa_user_id.id == user.id
            or room.alumni_user_id.id == user.id
            or user.mentorize_role == 'admin'
        )

    # ---------- public pages ----------
    @http.route(['/', '/home', '/mentorize'], type='http', auth='public', website=True, sitemap=False)
    def landing(self, **kwargs):
        if not request.env.user._is_public() and kwargs.get('force') != '1':
            if request.env.user.mentorize_role == 'alumni':
                return request.redirect('/alumni/dashboard')
            if request.env.user.mentorize_role == 'admin':
                return request.redirect('/admin/dashboard')
            return request.redirect('/dashboard')

        return request.render('mentorize.page_landing', {})

    @http.route(['/login', '/mentorize/login'], type='http', auth='public', website=True, sitemap=False)
    def login(self, **kwargs):
        selected_role = kwargs.get('role') if kwargs.get('role') in ['mahasiswa', 'alumni'] else 'mahasiswa'

        return request.render('mentorize.page_login', {
            'error': kwargs.get('error') or False,
            'registered': kwargs.get('registered') or False,
            'reset': kwargs.get('reset') or False,
            'selected_role': selected_role,
            'old_email': kwargs.get('email') or '',
        })

    @http.route(['/login/submit', '/mentorize/login/submit'], type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def login_submit(self, **kwargs):
        email = (kwargs.get('email') or '').strip().lower()
        password = kwargs.get('password') or ''
        selected_role = kwargs.get('role') if kwargs.get('role') in ['mahasiswa', 'alumni'] else False

        def render_error(message):
            return request.render('mentorize.page_login', {
                'error': message,
                'registered': False,
                'reset': False,
                'selected_role': selected_role or 'mahasiswa',
                'old_email': email,
            })

        try:
            uid = request.session.authenticate(request.db, email, password)

            if uid:
                try:
                    request.update_env(user=uid)
                except Exception:
                    pass

                user = request.env['res.users'].sudo().browse(uid)
                actual_role = self._infer_user_role(user, selected_role=selected_role)

                if selected_role and actual_role != selected_role:
                    request.session.logout(keep_db=True)
                    label = 'Alumni' if actual_role == 'alumni' else 'Mahasiswa'
                    return render_error('Akun ini terdaftar sebagai %s, bukan role yang dipilih.' % label)

                self._sync_user_role(user, actual_role)

                try:
                    request.update_env(user=uid)
                except Exception:
                    pass

                return self._redirect_after_login()

        except AccessDenied:
            pass
        except Exception:
            pass

        return render_error('Email atau password salah.')

    @http.route(['/register', '/mentorize/register'], type='http', auth='public', website=True, sitemap=False)
    def register(self, **kwargs):
        selected_role = kwargs.get('role') if kwargs.get('role') in ['mahasiswa', 'alumni'] else 'mahasiswa'

        return request.render('mentorize.page_register', {
            'old': {},
            'selected_role': selected_role,
            'error': False
        })

    @http.route(['/register/submit', '/mentorize/register/submit'], type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def register_submit(self, **kwargs):
        name = (kwargs.get('name') or '').strip()
        email = (kwargs.get('email') or '').strip().lower()
        password = kwargs.get('password') or ''
        confirm_password = kwargs.get('confirm_password') or ''
        role = kwargs.get('role') if kwargs.get('role') in ['mahasiswa', 'alumni'] else 'mahasiswa'
        identity = (kwargs.get('identity') or '').strip()

        User = request.env['res.users'].sudo()

        def render_error(message):
            return request.render('mentorize.page_register', {
                'error': message,
                'old': kwargs,
                'selected_role': role
            })

        if not name or not email or not identity or not password:
            return render_error('Semua field wajib diisi.')

        if password != confirm_password:
            return render_error('Password dan konfirmasi password tidak sama.')

        if User.search(['|', ('login', '=', email), ('email', '=', email)], limit=1):
            return render_error('Email sudah terdaftar.')

        if role == 'mahasiswa':
            if request.env['mentorize.mahasiswa'].sudo().search([('nim', '=', identity)], limit=1) or User.search([('nim', '=', identity)], limit=1):
                return render_error('NIM sudah pernah dipakai untuk daftar.')

            ok, msg = self._verify_mahasiswa_identity(identity, name)
            if not ok:
                return render_error(msg)

        else:
            if request.env['mentorize.alumni'].sudo().search([('kapa', '=', identity)], limit=1) or User.search([('kapa', '=', identity)], limit=1):
                return render_error('KAPA sudah pernah dipakai untuk daftar.')

            ok, msg = self._verify_alumni_identity(identity, name)
            if not ok:
                return render_error(msg)

        # FIX PERMANEN:
        # User baru wajib punya base.group_portal + group role Mentorize.
        # Jangan cuma group Mentorize, karena nanti user tidak punya akses website.
        portal_group = request.env.ref('base.group_portal', raise_if_not_found=False)

        role_group_xmlid = 'mentorize.group_mentorize_mahasiswa' if role == 'mahasiswa' else 'mentorize.group_mentorize_alumni'
        role_group = request.env.ref(role_group_xmlid, raise_if_not_found=False)

        group_ids = []
        if portal_group:
            group_ids.append(portal_group.id)
        if role_group:
            group_ids.append(role_group.id)

        vals = {
            'name': name,
            'login': email,
            'email': email,
            'password': password,
            'mentorize_role': role,
            'mentorize_notification_email': True,
            'groups_id': [(6, 0, group_ids)],
        }

        if role == 'mahasiswa':
            vals.update({
                'nim': identity,
                'is_verified': True,
            })
        else:
            vals.update({
                'kapa': identity,
                'is_verified': True,
            })

        try:
            new_user = User.create(vals)

            if role == 'mahasiswa':
                request.env['mentorize.mahasiswa'].sudo().create({
                    'user_id': new_user.id,
                    'nim': identity,
                })
            else:
                request.env['mentorize.alumni'].sudo().create({
                    'user_id': new_user.id,
                    'kapa': identity,
                    'is_verified': True,
                    'availability': 'available',
                })

        except Exception as e:
            return render_error('Terjadi kesalahan saat membuat akun: %s' % e)

        return request.redirect('/login?registered=1&role=%s' % role)

    @http.route(['/forgot-password', '/mentorize/forgot-password'], type='http', auth='public', website=True, sitemap=False)
    def forgot_password(self, **kwargs):
        return request.render('mentorize.page_forgot_password', {
            'success': False,
            'error': False
        })

    @http.route(['/forgot-password/submit', '/mentorize/forgot-password/submit'], type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def forgot_password_submit(self, **kwargs):
        email = (kwargs.get('email') or '').strip().lower()
        user = request.env['res.users'].sudo().search(['|', ('login', '=', email), ('email', '=', email)], limit=1)

        if not user:
            return request.render('mentorize.page_forgot_password', {
                'success': False,
                'error': 'Email tidak ditemukan.'
            })

        try:
            user.sudo().action_reset_password()
            return request.render('mentorize.page_forgot_password', {
                'success': True,
                'error': False
            })
        except Exception as e:
            return request.render('mentorize.page_forgot_password', {
                'success': False,
                'error': 'Gagal mengirim email reset. Pastikan Outgoing Mail Server / SMTP Odoo sudah diatur. Detail: %s' % e
            })

    # ---------- dashboard ----------
    @http.route('/dashboard', type='http', auth='user', website=True, sitemap=False)
    def dashboard(self, **kwargs):
        role = self._sync_user_role(request.env.user)

        if role == 'alumni':
            return request.redirect('/alumni/dashboard')
        if role == 'admin':
            return request.redirect('/admin/dashboard')

        return self.dashboard_mahasiswa(**kwargs)

    @http.route(['/mentorize/mahasiswa/dashboard'], type='http', auth='user', website=True, sitemap=False)
    def old_dashboard_mahasiswa(self, **kwargs):
        return request.redirect('/dashboard')

    @http.route('/dashboard/mahasiswa', type='http', auth='user', website=True, sitemap=False)
    def dashboard_mahasiswa_alias(self, **kwargs):
        return self.dashboard_mahasiswa(**kwargs)

    def dashboard_mahasiswa(self, **kwargs):
        if self._infer_user_role(request.env.user) == 'alumni':
            return request.redirect('/alumni/dashboard')

        mahasiswa = self._ensure_profile('mahasiswa')

        if not mahasiswa.profile_complete:
            return request.redirect('/profile/setup')

        Request = request.env['mentorize.request'].sudo()
        Session = request.env['mentorize.session'].sudo()

        pending_requests = Request.search([('mahasiswa_id', '=', mahasiswa.id), ('status', '=', 'pending')], limit=5)
        active_requests = Request.search([('mahasiswa_id', '=', mahasiswa.id), ('status', '=', 'approved')], limit=5)

        upcoming_sessions = Session.search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', 'in', ['scheduled', 'active', 'end_requested'])
        ], order='tanggal_mentoring asc', limit=6)

        completed_sessions = Session.search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'completed')
        ], order='completed_at desc, tanggal_mentoring desc', limit=5)

        recommended = self._recommend_mentors(mahasiswa, limit=6)

        values = self._layout_values('dashboard')
        values.update({
            'mahasiswa': mahasiswa,
            'recommended_mentors': recommended,
            'pending_requests': pending_requests,
            'active_requests': active_requests,
            'upcoming_sessions': upcoming_sessions,
            'completed_sessions': completed_sessions,
            'stats': {
                'mentor_rekomendasi': len(recommended),
                'request_pending': len(pending_requests),
                'sesi_aktif': len(upcoming_sessions),
                'sesi_selesai': len(completed_sessions),
            },
            'today': fields.Date.context_today(request.env.user),
            'max_date': fields.Date.context_today(request.env.user) + timedelta(days=90),
            'today_min': fields.Date.to_string(fields.Date.context_today(request.env.user)) + 'T00:00',
            'max_datetime': fields.Date.to_string(fields.Date.context_today(request.env.user) + timedelta(days=90)) + 'T23:59',
        })

        return request.render('mentorize.dashboard_mahasiswa', values)

    @http.route(['/alumni/dashboard', '/mentorize/alumni/dashboard'], type='http', auth='user', website=True, sitemap=False)
    def dashboard_alumni(self, **kwargs):
        if self._infer_user_role(request.env.user) != 'alumni':
            return request.redirect('/dashboard')

        alumni = self._ensure_profile('alumni')

        if not alumni.profile_complete:
            return request.redirect('/alumni/profile/setup')

        Request = request.env['mentorize.request'].sudo()
        Session = request.env['mentorize.session'].sudo()

        requests_list = Request.search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'pending')
        ], order='tanggal_request desc')

        upcoming_sessions = Session.search([
            ('alumni_id', '=', alumni.id),
            ('status', 'in', ['scheduled', 'active', 'end_requested'])
        ], order='tanggal_mentoring asc')

        completed_sessions = Session.search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'completed')
        ], order='completed_at desc, tanggal_mentoring desc', limit=5)

        end_requests = Session.search([
            ('alumni_id', '=', alumni.id),
            ('status', '=', 'end_requested')
        ], order='end_requested_at desc')

        values = self._layout_values('dashboard')
        values.update({
            'alumni': alumni,
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
            'requests': requests_list,
            'upcoming_sessions': upcoming_sessions,
            'completed_sessions': completed_sessions,
            'end_requests': end_requests,
            'stats': {
                'permintaan_baru': len(requests_list),
                'sesi_aktif': len(upcoming_sessions),
                'sesi_selesai': len(completed_sessions),
                'rating': alumni.rating,
            },
        })

        return request.render('mentorize.dashboard_alumni', values)

    @http.route('/admin/dashboard', type='http', auth='user', website=True, sitemap=False)
    def admin_dashboard(self, **kwargs):
        values = self._layout_values('dashboard')
        values.update({
            'total_mahasiswa': request.env['mentorize.mahasiswa'].sudo().search_count([]),
            'total_alumni': request.env['mentorize.alumni'].sudo().search_count([]),
            'total_requests': request.env['mentorize.request'].sudo().search_count([]),
            'total_sessions': request.env['mentorize.session'].sudo().search_count([]),
        })
        return request.render('mentorize.dashboard_admin', values)

    # ---------- profile ----------
    @http.route(['/profile/setup', '/profile', '/mentorize/mahasiswa/profil'], type='http', auth='user', website=True, sitemap=False)
    def profile_mahasiswa(self, **kwargs):
        if self._infer_user_role(request.env.user) == 'alumni':
            return request.redirect('/alumni/profile/setup')

        mahasiswa = self._ensure_profile('mahasiswa')
        all_minat = request.env['mentorize.minat'].sudo().search([])
        all_skill = request.env['mentorize.skill'].sudo().search([])

        values = self._layout_values('profile')
        values.update({
            'mahasiswa': mahasiswa,
            'all_minat': all_minat,
            'all_skill': all_skill,
            'selected_minat_ids': mahasiswa.minat_ids.ids,
            'selected_skill_ids': mahasiswa.skill_ids.ids,
            'is_setup': request.httprequest.path in ['/profile/setup'],
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
        })

        return request.render('mentorize.page_profile_mahasiswa', values)

    @http.route(['/profile/edit', '/mentorize/mahasiswa/profil/edit'], type='http', auth='user', website=True, sitemap=False)
    def profile_edit_alias(self, **kwargs):
        return self.profile_mahasiswa(**kwargs)

    @http.route(['/profile/update', '/mentorize/mahasiswa/profil/update'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def profile_update(self, **kwargs):
        mahasiswa = self._ensure_profile('mahasiswa')
        user = request.env.user

        minat_ids = [int(x) for x in request.httprequest.form.getlist('minat_ids') if x]
        skill_ids = [int(x) for x in request.httprequest.form.getlist('skill_ids') if x]
        semester = kwargs.get('semester') or '0'

        try:
            user_vals = {
                'name': kwargs.get('name') or user.name,
                'nim': kwargs.get('nim') or user.nim,
                'jurusan': kwargs.get('jurusan') or user.jurusan,
                'tujuan_karir': kwargs.get('tujuan_karir') or '',
                'bio': kwargs.get('bio') or '',
            }

            photo = request.httprequest.files.get('photo')
            if photo and photo.filename:
                user_vals['image_1920'] = base64.b64encode(photo.read())

            user.sudo().write(user_vals)

            mahasiswa.sudo().write({
                'nim': kwargs.get('nim') or '',
                'jurusan': kwargs.get('jurusan') or '',
                'semester': int(semester) if semester.isdigit() else 0,
                'tujuan_karir': kwargs.get('tujuan_karir') or '',
                'bio': kwargs.get('bio') or '',
                'minat_ids': [(6, 0, minat_ids)],
                'skill_ids': [(6, 0, skill_ids)],
            })

            return request.redirect('/dashboard' if mahasiswa.profile_complete else '/profile?success=1')

        except Exception as e:
            return request.redirect('/profile?error=%s' % str(e))

    @http.route('/alumni/profile/setup', type='http', auth='user', website=True, sitemap=False)
    def alumni_profile(self, **kwargs):
        if self._infer_user_role(request.env.user) != 'alumni':
            return request.redirect('/profile')

        alumni = self._ensure_profile('alumni')

        values = self._layout_values('profile')
        values.update({
            'alumni': alumni,
            'all_minat': request.env['mentorize.minat'].sudo().search([]),
            'all_skill': request.env['mentorize.skill'].sudo().search([]),
            'selected_minat_ids': alumni.minat_ids.ids,
            'selected_skill_ids': alumni.skill_ids.ids,
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
        })

        return request.render('mentorize.page_profile_alumni', values)

    @http.route('/alumni/profile/update', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def alumni_profile_update(self, **kwargs):
        alumni = self._ensure_profile('alumni')
        user = request.env.user

        minat_ids = [int(x) for x in request.httprequest.form.getlist('minat_ids') if x]
        skill_ids = [int(x) for x in request.httprequest.form.getlist('skill_ids') if x]

        try:
            user_vals = {
                'name': kwargs.get('name') or user.name,
                'kapa': kwargs.get('kapa') or user.kapa,
                'bio': kwargs.get('deskripsi') or '',
            }

            photo = request.httprequest.files.get('photo')
            if photo and photo.filename:
                user_vals['image_1920'] = base64.b64encode(photo.read())

            user.sudo().write(user_vals)

            alumni.sudo().write({
                'kapa': kwargs.get('kapa') or '',
                'tempat_bekerja': kwargs.get('tempat_bekerja') or '',
                'pekerjaan': kwargs.get('pekerjaan') or '',
                'tahun_lulus': int(kwargs.get('tahun_lulus') or 0),
                'availability': kwargs.get('availability') or 'available',
                'slot_mentoring': int(kwargs.get('slot_mentoring') or 3),
                'deskripsi': kwargs.get('deskripsi') or '',
                'minat_ids': [(6, 0, minat_ids)],
                'skill_ids': [(6, 0, skill_ids)],
            })

            return request.redirect('/alumni/dashboard' if alumni.profile_complete else '/alumni/profile/setup?success=1')

        except Exception as e:
            return request.redirect('/alumni/profile/setup?error=%s' % str(e))

    # ---------- settings ----------
    @http.route('/settings', type='http', auth='user', website=True, sitemap=False)
    def settings(self, **kwargs):
        values = self._layout_values('settings')
        values.update({
            'success': kwargs.get('success'),
            'error': kwargs.get('error')
        })
        return request.render('mentorize.page_settings', values)

    @http.route('/settings/account', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def settings_account(self, **kwargs):
        new_email = (kwargs.get('email') or request.env.user.email or '').strip().lower()

        vals = {
            'name': kwargs.get('name') or request.env.user.name,
            'email': new_email,
            'login': new_email or request.env.user.login,
            'mentorize_notification_email': True if kwargs.get('mentorize_notification_email') else False,
        }

        photo = request.httprequest.files.get('photo')
        if photo and photo.filename:
            vals['image_1920'] = base64.b64encode(photo.read())

        request.env.user.sudo().write(vals)

        return request.redirect('/settings?success=1')

    @http.route('/settings/password', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def settings_password(self, **kwargs):
        old = kwargs.get('old_password') or ''
        new = kwargs.get('new_password') or ''
        confirm = kwargs.get('confirm_password') or ''

        if new != confirm:
            return request.redirect('/settings?error=Konfirmasi password baru tidak sama')

        try:
            request.session.authenticate(request.db, request.env.user.login, old)
            request.env.user.sudo().write({'password': new})
            return request.redirect('/settings?success=1')
        except Exception:
            return request.redirect('/settings?error=Password lama salah')

    # ---------- mentor, request, calendar ----------
    @http.route(['/mentors', '/mentorize/mahasiswa/cari-mentor'], type='http', auth='user', website=True, sitemap=False)
    def mentors(self, **kwargs):
        if self._infer_user_role(request.env.user) == 'alumni':
            return request.redirect('/alumni/dashboard')

        mahasiswa = self._ensure_profile('mahasiswa')

        if not mahasiswa.profile_complete:
            return request.redirect('/profile/setup')

        query = (kwargs.get('q') or '').strip()
        Alumni = request.env['mentorize.alumni'].sudo()

        if query:
            mentors = Alumni.search([
                '|', '|',
                ('user_id.name', 'ilike', query),
                ('pekerjaan', 'ilike', query),
                ('deskripsi', 'ilike', query)
            ])
        else:
            mentors = self._recommend_mentors(mahasiswa, limit=30)

        values = self._layout_values('mentors')
        values.update({
            'mahasiswa': mahasiswa,
            'mentors': mentors,
            'q': query,
            'today': fields.Date.context_today(request.env.user),
            'max_date': fields.Date.context_today(request.env.user) + timedelta(days=90),
            'today_min': fields.Date.to_string(fields.Date.context_today(request.env.user)) + 'T00:00',
            'max_datetime': fields.Date.to_string(fields.Date.context_today(request.env.user) + timedelta(days=90)) + 'T23:59',
            'error': kwargs.get('error'),
            'success': kwargs.get('success'),
        })

        return request.render('mentorize.page_mentors', values)

    @http.route('/mentoring/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def mentoring_request(self, **kwargs):
        mahasiswa = self._ensure_profile('mahasiswa')
        alumni_id = int(kwargs.get('alumni_id') or 0)
        topik = (kwargs.get('topik') or '').strip()
        deskripsi = kwargs.get('deskripsi') or ''
        date_str = kwargs.get('requested_datetime') or ''

        try:
            requested_dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except Exception:
            return request.redirect('/mentors?error=Format tanggal tidak valid')

        today = fields.Date.context_today(request.env.user)

        if requested_dt.date() < today or requested_dt.date() > today + timedelta(days=90):
            return request.redirect('/mentors?error=Tanggal mentoring harus antara hari ini sampai 90 hari ke depan')

        alumni = request.env['mentorize.alumni'].sudo().browse(alumni_id)

        if not alumni.exists() or not topik:
            return request.redirect('/mentors?error=Data request belum lengkap')

        req = request.env['mentorize.request'].sudo().create({
            'mahasiswa_id': mahasiswa.id,
            'alumni_id': alumni.id,
            'topik': topik,
            'deskripsi': deskripsi,
            'requested_datetime': requested_dt,
            'status': 'pending',
        })

        request.env['mentorize.notification'].sudo().create_notification(
            alumni.user_id,
            'Request mentoring baru',
            '%s mengajukan mentoring tentang %s.' % (mahasiswa.name, topik),
            notif_type='request_new',
            url='/alumni/dashboard',
        )

        return request.redirect('/dashboard?success=request')

    @http.route(['/alumni/request/<int:req_id>/approve', '/mentorize/alumni/request/<int:req_id>/approve'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_request(self, req_id, **kwargs):
        req = request.env['mentorize.request'].sudo().browse(req_id)
        alumni = self._current_alumni()

        if req.exists() and alumni and req.alumni_id.id == alumni.id:
            conflict = request.env['mentorize.session'].sudo().search_count([
                ('alumni_id', '=', alumni.id),
                ('tanggal_mentoring', '=', req.requested_datetime),
                ('status', 'in', ['scheduled', 'active', 'end_requested']),
            ])

            if conflict:
                return request.redirect('/alumni/dashboard?error=Jadwal tersebut sudah terisi. Tolak request ini atau minta mahasiswa membuat request baru.')

            req.action_approve()
            return request.redirect('/alumni/dashboard?success=Request mentoring diterima dan room chat sudah aktif.')

        return request.redirect('/alumni/dashboard')

    @http.route(['/alumni/request/<int:req_id>/reject', '/mentorize/alumni/request/<int:req_id>/reject'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def reject_request(self, req_id, **kwargs):
        req = request.env['mentorize.request'].sudo().browse(req_id)
        alumni = self._current_alumni()

        if req.exists() and alumni and req.alumni_id.id == alumni.id:
            req.action_reject()
            return request.redirect('/alumni/dashboard?success=Request mentoring ditolak.')

        return request.redirect('/alumni/dashboard')

    # ---------- chat ----------
    @http.route(['/chat', '/mentorize/mahasiswa/chat'], type='http', auth='user', website=True, sitemap=False)
    def chat(self, **kwargs):
        room_id = int(kwargs.get('room_id') or 0)
        user = request.env.user

        domain = ['|', ('mahasiswa_user_id', '=', user.id), ('alumni_user_id', '=', user.id)]
        rooms = request.env['mentorize.roomchat'].sudo().search(domain)

        selected_room = request.env['mentorize.roomchat'].sudo().browse(room_id) if room_id else (rooms[:1] if rooms else False)

        if selected_room and not self._room_allowed(selected_room):
            selected_room = rooms[:1] if rooms else False

        values = self._layout_values('chat')
        values.update({
            'rooms': rooms,
            'selected_room': selected_room,
        })

        return request.render('mentorize.page_chat', values)

    @http.route('/chat/data', type='http', auth='user', website=False, methods=['GET'], csrf=False)
    def chat_data(self, **kwargs):
        room_id = int(kwargs.get('room_id') or 0)
        after_id = int(kwargs.get('after_id') or 0)

        room = request.env['mentorize.roomchat'].sudo().browse(room_id)

        if not room.exists() or not self._room_allowed(room):
            return self._json({'success': False, 'messages': []}, status=403)

        domain = [('room_id', '=', room.id)]
        if after_id:
            domain.append(('id', '>', after_id))

        messages = request.env['mentorize.message'].sudo().search(domain, order='id asc')

        data = []
        for msg in messages:
            data.append({
                'id': msg.id,
                'sender_id': msg.sender_id.id,
                'sender_name': msg.sender_id.name,
                'body': msg.isi_pesan,
                'time': fields.Datetime.context_timestamp(request.env.user, msg.waktu_kirim).strftime('%H:%M'),
                'is_me': msg.sender_id.id == request.env.user.id,
            })

        return self._json({'success': True, 'messages': data})

    @http.route('/chat/send', type='http', auth='user', website=False, methods=['POST'], csrf=False)
    def chat_send(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or {}
        room_id = int(payload.get('room_id') or kwargs.get('room_id') or 0)
        message = (payload.get('message') or kwargs.get('message') or '').strip()

        room = request.env['mentorize.roomchat'].sudo().browse(room_id)

        if not room.exists() or not self._room_allowed(room) or not message:
            return self._json({'success': False}, status=403)

        msg = request.env['mentorize.message'].sudo().create({
            'room_id': room.id,
            'sender_id': request.env.user.id,
            'isi_pesan': message,
        })

        partner = room.alumni_user_id if room.mahasiswa_user_id.id == request.env.user.id else room.mahasiswa_user_id

        request.env['mentorize.notification'].sudo().create_notification(
            partner,
            'Pesan baru',
            '%s mengirim pesan baru.' % request.env.user.name,
            notif_type='chat',
            url='/chat?room_id=%s' % room.id,
        )

        return self._json({'success': True, 'message_id': msg.id})

    # ---------- ending session, summary, history ----------
    @http.route('/session/<int:session_id>/end/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def request_end_session(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and mahasiswa and session.mahasiswa_id.id == mahasiswa.id:
            session.write({
                'status': 'end_requested',
                'end_request_note': kwargs.get('note') or '',
                'end_requested_at': fields.Datetime.now(),
            })

            request.env['mentorize.notification'].sudo().create_notification(
                session.alumni_id.user_id,
                'Pengajuan akhir sesi',
                '%s mengajukan akhir sesi mentoring.' % mahasiswa.name,
                notif_type='session_end_requested',
                url='/alumni/dashboard',
            )

        return request.redirect('/dashboard')

    @http.route('/session/<int:session_id>/end/approve', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_end_session(self, session_id, **kwargs):
        alumni = self._current_alumni()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and alumni and session.alumni_id.id == alumni.id:
            session.write({
                'status': 'completed',
                'completed_at': fields.Datetime.now()
            })

            session.request_id.write({
                'status': 'done'
            })

            if session.request_id.room_chat_id:
                session.request_id.room_chat_id.write({
                    'status': 'closed'
                })

            request.env['mentorize.notification'].sudo().create_notification(
                session.mahasiswa_id.user_id,
                'Sesi mentoring selesai',
                'Sesi mentoring kamu telah disetujui selesai. Silakan isi rangkuman mentoring.',
                notif_type='session_completed',
                url='/summary/%s' % session.id,
            )

        return request.redirect('/alumni/dashboard')

    @http.route('/session/<int:session_id>/end/reject', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def reject_end_session(self, session_id, **kwargs):
        alumni = self._current_alumni()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and alumni and session.alumni_id.id == alumni.id:
            session.write({
                'status': 'active'
            })

            request.env['mentorize.notification'].sudo().create_notification(
                session.mahasiswa_id.user_id,
                'Pengajuan akhir sesi belum disetujui',
                'Mentor merasa sesi masih perlu dilanjutkan.',
                notif_type='info',
                url='/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''),
            )

        return request.redirect('/alumni/dashboard')

    @http.route('/summary/<int:session_id>', type='http', auth='user', website=True, sitemap=False)
    def summary(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if not session.exists() or not mahasiswa or session.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/dashboard')

        values = self._layout_values('history')
        values.update({
            'session': session,
            'success': kwargs.get('success')
        })

        return request.render('mentorize.page_summary', values)

    @http.route('/summary/<int:session_id>/save', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def summary_save(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and mahasiswa and session.mahasiswa_id.id == mahasiswa.id:
            session.write({
                'summary_saved': True,
                'summary_topic': kwargs.get('summary_topic') or session.topik,
                'summary_learnings': kwargs.get('summary_learnings') or '',
                'summary_advice': kwargs.get('summary_advice') or '',
                'summary_next_steps': kwargs.get('summary_next_steps') or '',
                'summary_notes': kwargs.get('summary_notes') or '',
            })

            rating = int(kwargs.get('rating') or 5)
            komentar = kwargs.get('komentar') or ''

            feedback = request.env['mentorize.feedback'].sudo().create({
                'session_id': session.id,
                'alumni_id': session.alumni_id.id,
                'mahasiswa_id': session.mahasiswa_id.id,
                'rating': rating,
                'komentar': komentar,
            })

            session.feedback_id = feedback.id

        return request.redirect('/history')

    @http.route('/history', type='http', auth='user', website=True, sitemap=False)
    def history(self, **kwargs):
        mahasiswa = self._current_mahasiswa()

        if not mahasiswa:
            return request.redirect('/dashboard')

        sessions = request.env['mentorize.session'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id),
            ('status', '=', 'completed')
        ], order='completed_at desc, tanggal_mentoring desc')

        values = self._layout_values('history')
        values.update({
            'sessions': sessions
        })

        return request.render('mentorize.page_history', values)

    @http.route('/history/<int:session_id>', type='http', auth='user', website=True, sitemap=False)
    def history_detail(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if not session.exists() or not mahasiswa or session.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/history')

        values = self._layout_values('history')
        values.update({
            'session': session
        })

        return request.render('mentorize.page_history_detail', values)

    # ---------- notifications ----------
    @http.route('/notifications/read', type='http', auth='user', website=False, methods=['POST'], csrf=False)
    def notifications_read(self, **kwargs):
        request.env['mentorize.notification'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('is_read', '=', False)
        ]).write({
            'is_read': True
        })

        return self._json({'success': True})

    @http.route('/logout/confirm', type='http', auth='user', website=True, sitemap=False)
    def logout_confirm(self, **kwargs):
        return request.redirect('/web/session/logout?redirect=/login')