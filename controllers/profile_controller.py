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


class MentorizeProfileController(MentorizeBaseController):
    # Semua method di class ini adalah route Odoo untuk fitur yang sesuai nama file.
    # ---------- profile ----------
    # Route profile_mahasiswa: menangani request web untuk fitur ini.
    @http.route(['/profile/setup', '/profile', '/mentorize/mahasiswa/profil'], type='http', auth='user', website=True, sitemap=False)
    def profile_mahasiswa(self, **kwargs):
        if self._infer_user_role(request.env.user) == 'alumni':
            return request.redirect('/alumni/profile/setup')

        mahasiswa = self._ensure_profile('mahasiswa')
        all_minat = self._unique_records_by_name(request.env['mentorize.minat'].sudo().search([]), mahasiswa.minat_ids.ids)
        all_skill = self._unique_records_by_name(request.env['mentorize.skill'].sudo().search([]), mahasiswa.skill_ids.ids)

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

    # Route profile_edit_alias: menangani request web untuk fitur ini.
    @http.route(['/profile/edit', '/mentorize/mahasiswa/profil/edit'], type='http', auth='user', website=True, sitemap=False)
    def profile_edit_alias(self, **kwargs):
        return self.profile_mahasiswa(**kwargs)

    # Route profile_update: menangani request web untuk fitur ini.
    @http.route(['/profile/update', '/mentorize/mahasiswa/profil/update'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def profile_update(self, **kwargs):
        mahasiswa = self._ensure_profile('mahasiswa')
        user = request.env.user

        minat_ids = [int(x) for x in request.httprequest.form.getlist('minat_ids') if x]
        skill_ids = [int(x) for x in request.httprequest.form.getlist('skill_ids') if x]
        semester = kwargs.get('semester') or '0'

        try:
            name = (kwargs.get('name') or '').strip()
            notification_email = (kwargs.get('email') or '').strip().lower()
            if not name or name == (user.login or '').strip():
                return request.redirect('/profile?error=Nama lengkap wajib diisi dan tidak boleh sama dengan NIM bawaan SSO')
            if not self._is_valid_email(notification_email) or notification_email == (user.login or '').strip().lower():
                return request.redirect('/profile?error=Email notifikasi wajib diisi dengan format email yang valid')
            if not minat_ids or not skill_ids:
                return request.redirect('/profile?error=Minimal pilih 1 minat dan 1 skill')
            if not (kwargs.get('nim') or '').strip() or not (kwargs.get('jurusan') or '').strip() or not (kwargs.get('tujuan_karir') or '').strip() or not (kwargs.get('bio') or '').strip():
                return request.redirect('/profile?error=Semua field bertanda bintang wajib diisi')

            user_vals = {
                'name': name,
                'email': notification_email,
                'nim': kwargs.get('nim') or user.nim,
                'jurusan': kwargs.get('jurusan') or user.jurusan,
                'tujuan_karir': kwargs.get('tujuan_karir') or '',
                'bio': kwargs.get('bio') or '',
                'mentorize_notification_email': True if kwargs.get('mentorize_notification_email') else False,
            }

            photo = request.httprequest.files.get('photo')
            if photo and photo.filename:
                ok, error, info = self._validate_profile_photo(photo)
                if not ok:
                    return request.redirect('/profile?error=%s' % error)
                user_vals['image_1920'] = base64.b64encode(info['data'])

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

    # Route alumni_profile: menangani request web untuk fitur ini.
    @http.route('/alumni/profile/setup', type='http', auth='user', website=True, sitemap=False)
    def alumni_profile(self, **kwargs):
        if self._infer_user_role(request.env.user) != 'alumni':
            return request.redirect('/profile')

        alumni = self._ensure_profile('alumni')

        values = self._layout_values('profile')
        values.update({
            'alumni': alumni,
            'all_minat': self._unique_records_by_name(request.env['mentorize.minat'].sudo().search([]), alumni.minat_ids.ids),
            'all_skill': self._unique_records_by_name(request.env['mentorize.skill'].sudo().search([]), alumni.skill_ids.ids),
            'selected_minat_ids': alumni.minat_ids.ids,
            'selected_skill_ids': alumni.skill_ids.ids,
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
        })

        return request.render('mentorize.page_profile_alumni', values)

    # Route alumni_profile_update: menangani request web untuk fitur ini.
    @http.route('/alumni/profile/update', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def alumni_profile_update(self, **kwargs):
        alumni = self._ensure_profile('alumni')
        user = request.env.user

        minat_ids = [int(x) for x in request.httprequest.form.getlist('minat_ids') if x]
        skill_ids = [int(x) for x in request.httprequest.form.getlist('skill_ids') if x]
        experiences = self._collect_alumni_experience_vals(kwargs)

        try:
            name = (kwargs.get('name') or '').strip()
            notification_email = (kwargs.get('email') or '').strip().lower()
            if not name or name == (user.login or '').strip():
                return request.redirect('/alumni/profile/setup?error=Nama lengkap wajib diisi dan tidak boleh sama dengan NIM bawaan SSO')
            if not self._is_valid_email(notification_email) or notification_email == (user.login or '').strip().lower():
                return request.redirect('/alumni/profile/setup?error=Email notifikasi wajib diisi dengan format email yang valid')
            if not minat_ids or not skill_ids:
                return request.redirect('/alumni/profile/setup?error=Minimal pilih 1 bidang mentoring dan 1 skill')
            if not (kwargs.get('kapa') or '').strip() or not (kwargs.get('pekerjaan') or '').strip() or not (kwargs.get('tempat_bekerja') or '').strip() or not (kwargs.get('deskripsi') or '').strip():
                return request.redirect('/alumni/profile/setup?error=Semua field bertanda bintang wajib diisi')
            if self._count_complete_experiences(experiences) < 3:
                return request.redirect('/alumni/profile/setup?error=Minimal isi 3 pengalaman kerja lengkap: perusahaan, posisi, dan tahun.')

            user_vals = {
                'name': name,
                'email': notification_email,
                'kapa': kwargs.get('kapa') or user.kapa,
                'bio': kwargs.get('deskripsi') or '',
                'mentorize_notification_email': True if kwargs.get('mentorize_notification_email') else False,
            }

            photo = request.httprequest.files.get('photo')
            if photo and photo.filename:
                ok, error, info = self._validate_profile_photo(photo)
                if not ok:
                    return request.redirect('/alumni/profile/setup?error=%s' % error)
                user_vals['image_1920'] = base64.b64encode(info['data'])

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

            # Simpan ulang pengalaman kerja agar alumni bisa menambah/mengubah banyak pengalaman sekaligus.
            alumni.experience_ids.sudo().unlink()
            for exp_vals in experiences:
                request.env['mentorize.experience'].sudo().create(dict(exp_vals, alumni_id=alumni.id))

            return request.redirect('/alumni/dashboard' if alumni.profile_complete else '/alumni/profile/setup?success=1')

        except Exception as e:
            return request.redirect('/alumni/profile/setup?error=%s' % str(e))

    # ---------- settings ----------
    # Route settings: menangani request web untuk fitur ini.
    @http.route('/settings', type='http', auth='user', website=True, sitemap=False)
    def settings(self, **kwargs):
        role = self._infer_user_role(request.env.user)
        values = self._admin_base_values('settings') if role == 'admin' else self._layout_values('settings')
        values.update({
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
            'is_sso_account': role in ['mahasiswa', 'alumni'],
            'sso_reset_password_url': request.env['ir.config_parameter'].sudo().get_param(
                'mentorize.sso.reset_password_url',
                'https://service.unisayogya.ac.id/sso/resetpassword.php',
            ),
        })
        return request.render('mentorize.page_settings', values)

    # Route settings_account: menangani request web untuk fitur ini.
    @http.route('/settings/account', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def settings_account(self, **kwargs):
        user = request.env.user
        role = self._infer_user_role(user)
        new_email = (kwargs.get('email') or '').strip().lower()

        new_name = (kwargs.get('name') or '').strip()
        if role in ['mahasiswa', 'alumni']:
            if not new_name or new_name == (user.login or '').strip():
                return request.redirect('/settings?error=Nama wajib diisi dan tidak boleh sama dengan NIM bawaan SSO')
            if not self._is_valid_email(new_email) or new_email == (user.login or '').strip().lower():
                return request.redirect('/settings?error=Email notifikasi wajib diisi dengan format email yang valid')
        elif new_email and not self._is_valid_email(new_email):
            return request.redirect('/settings?error=Format email notifikasi tidak valid')

        vals = {
            'name': new_name or user.name,
            'email': new_email or user.email or '',
            'mentorize_notification_email': True if kwargs.get('mentorize_notification_email') else False,
        }

        # Untuk mahasiswa/alumni SSO, login tetap NIM dari SSO.
        # Email di sini hanya dipakai sebagai email notifikasi, bukan username login.
        if role == 'admin' and new_email:
            vals['login'] = new_email

        photo = request.httprequest.files.get('photo')
        if photo and photo.filename:
            ok, error, info = self._validate_profile_photo(photo)
            if not ok:
                return request.redirect('/settings?error=%s' % error)
            vals['image_1920'] = base64.b64encode(info['data'])

        user.sudo().write(vals)

        return request.redirect('/settings?success=1')

    # Route settings_password: menangani request web untuk fitur ini.
    @http.route('/settings/password', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def settings_password(self, **kwargs):
        role = self._infer_user_role(request.env.user)
        if role in ['mahasiswa', 'alumni']:
            return request.redirect('/settings?error=Akun mahasiswa/alumni menggunakan SSO. Reset password dilakukan melalui layanan SSO UNISA.')

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
