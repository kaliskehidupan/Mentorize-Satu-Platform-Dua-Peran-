# -*- coding: utf-8 -*-
# Controller ini hasil pemisahan dari main.py agar kode lebih mudah dicek dan dirawat.
# Setiap file menyimpan route sesuai kelompok fiturnya.

import base64
import json
from datetime import datetime, timedelta

from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import AccessDenied

from .base import MentorizeBaseController


class MentorizeAuthController(MentorizeBaseController):
    # Semua method di class ini adalah route Odoo untuk fitur yang sesuai nama file.
    # ---------- admin login ----------
    # Route admin_login: menangani request web untuk fitur ini.
    @http.route(['/admin/login', '/mentorize/admin/login'], type='http', auth='public', website=True, sitemap=False)
    def admin_login(self, **kwargs):
        if not request.env.user._is_public() and self._infer_user_role(request.env.user) == 'admin':
            return request.redirect('/admin/dashboard')
        return request.render('mentorize.page_admin_login', {
            'error': kwargs.get('error') or False,
            'old_email': kwargs.get('email') or '',
        })

    # Route admin_login_submit: menangani request web untuk fitur ini.
    @http.route(['/admin/login/submit', '/mentorize/admin/login/submit'], type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def admin_login_submit(self, **kwargs):
        email = (kwargs.get('email') or '').strip().lower()
        password = kwargs.get('password') or ''

        def render_error(message):
            return request.render('mentorize.page_admin_login', {
                'error': message,
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
                role = self._infer_user_role(user)
                admin_group = request.env.ref('mentorize.group_mentorize_admin', raise_if_not_found=False)
                is_admin = role == 'admin' or bool(admin_group and admin_group in user.sudo().groups_id)
                if not is_admin:
                    request.session.logout(keep_db=True)
                    return render_error('Akun ini tidak memiliki akses Admin Mentorize.')
                self._sync_user_role(user, 'admin')
                try:
                    request.update_env(user=uid)
                except Exception:
                    pass
                request.session['login_method'] = 'admin'
                self._log_activity('login', 'Admin login ke panel Mentorize.', 'res.users', user.id, user)
                return request.redirect('/admin/dashboard')
        except AccessDenied:
            pass
        except Exception:
            pass

        return render_error('Email atau password admin salah.')

    # ---------- public pages ----------
    # Route landing: menangani request web untuk fitur ini.
    @http.route(['/', '/home', '/mentorize'], type='http', auth='public', website=True, sitemap=False)
    def landing(self, **kwargs):
        if not request.env.user._is_public() and kwargs.get('force') != '1':
            if request.env.user.mentorize_role == 'alumni':
                return request.redirect('/alumni/dashboard')
            if request.env.user.mentorize_role == 'admin':
                return request.redirect('/admin/dashboard')
            return request.redirect('/dashboard')

        return request.render('mentorize.page_landing', {})

    # Route login pengguna biasa.
    # Mahasiswa dan alumni sekarang masuk menggunakan SSO UNISA.
    # Login manual lama tidak ditampilkan lagi, tetapi masih bisa dibuka untuk darurat dengan /login?manual=1.
    @http.route(['/login', '/mentorize/login'], type='http', auth='public', website=True, sitemap=False)
    def login(self, **kwargs):
        # Jika SSO server lama masih callback ke /login, teruskan parameternya ke handler SSO.
        if kwargs.get('code'):
            query_string = request.httprequest.query_string.decode('utf-8')
            return request.redirect('/sso/callback?%s' % query_string, code=303)

        if not request.env.user._is_public():
            return self._redirect_after_login()

        # Fallback manual hanya untuk development/darurat, tidak dipakai di UI normal.
        if kwargs.get('manual') == '1':
            selected_role = kwargs.get('role') if kwargs.get('role') in ['mahasiswa', 'alumni'] else 'mahasiswa'
            return request.render('mentorize.page_login', {
                'error': kwargs.get('error') or False,
                'registered': kwargs.get('registered') or False,
                'reset': kwargs.get('reset') or False,
                'selected_role': selected_role,
                'old_email': kwargs.get('email') or '',
            })

        return request.redirect('/sso/login', code=303)

    # Route login_submit: menangani request web untuk fitur ini.
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

    # Route register: menangani request web untuk fitur ini.
    @http.route(['/register', '/mentorize/register'], type='http', auth='public', website=True, sitemap=False)
    def register(self, **kwargs):
        selected_role = kwargs.get('role') if kwargs.get('role') in ['mahasiswa', 'alumni'] else 'mahasiswa'

        return request.render('mentorize.page_register', {
            'old': {},
            'selected_role': selected_role,
            'error': False
        })

    # Route register_submit: menangani request web untuk fitur ini.
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

    # Route forgot_password: reset password mahasiswa/alumni diarahkan ke SSO UNISA.
    @http.route(['/forgot-password', '/mentorize/forgot-password'], type='http', auth='public', website=True, sitemap=False)
    def forgot_password(self, **kwargs):
        reset_url = request.env['ir.config_parameter'].sudo().get_param(
            'mentorize.sso.reset_password_url',
            'https://service.unisayogya.ac.id/sso/resetpassword.php',
        )
        return request.redirect(reset_url, code=303, local=False)

    @http.route(['/forgot-password/submit', '/mentorize/forgot-password/submit'], type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def forgot_password_submit(self, **kwargs):
        reset_url = request.env['ir.config_parameter'].sudo().get_param(
            'mentorize.sso.reset_password_url',
            'https://service.unisayogya.ac.id/sso/resetpassword.php',
        )
        return request.redirect(reset_url, code=303, local=False)


    # Route logout bersama.
    # Admin kembali ke /admin/login, sedangkan user SSO diarahkan ke logout SSO UNISA.
    @http.route(['/logout/confirm', '/sso/logout'], type='http', auth='public', website=True, sitemap=False)
    def logout_confirm(self, **kwargs):
        login_method = request.session.get('login_method')
        db_name = request.session.db

        if login_method == 'admin':
            redirect_url = '/admin/login'
            is_external = False

        elif login_method == 'sso':
            base_url = request.httprequest.host_url.rstrip('/') + '/'
            post_logout = request.env['ir.config_parameter'].sudo().get_param(
                'mentorize.sso.post_logout_redirect_uri',
                base_url,
            )
            logout_url = request.env['ir.config_parameter'].sudo().get_param(
                'mentorize.sso.logout_url',
                'https://service.unisayogya.ac.id/sso/logout.php',
            )
            from urllib.parse import quote_plus
            redirect_url = '%s?redirect_uri=%s' % (logout_url, quote_plus(post_logout))
            is_external = redirect_url.startswith(('http://', 'https://'))

        else:
            redirect_url = '/'
            is_external = False

        request.session.logout(keep_db=True)
        request.session.db = db_name

        # PENTING:
        # Redirect eksternal ke SSO UNISA wajib local=False.
        # Kalau tidak, Odoo bisa mengubahnya menjadi route lokal localhost.
        return request.redirect(redirect_url, code=303, local=not is_external)

