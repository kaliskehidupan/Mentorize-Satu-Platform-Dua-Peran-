# -*- coding: utf-8 -*-
"""Controller khusus SSO UNISA untuk pengguna Mahasiswa/Alumni.

Catatan desain:
- Admin tidak memakai SSO; admin tetap login manual lewat /admin/login.
- Landing page tetap aman di route /, jadi SSO tidak menggunakan route /.
- Logic SSO diambil dari pola auth_controller versi SSO, bukan dari controllers/sso.py lama.
- Versi ini dibuat aman untuk struktur controller Odoo yang memakai beberapa class turunan
  MentorizeBaseController. Helper SSO utama dibuat sebagai function modul agar tidak
  bergantung pada lookup method lewat self.
"""

import base64
import hashlib
import json
import logging
import secrets
from urllib.parse import quote_plus

import requests as http_requests

from odoo import http
from odoo.http import request

from .base import MentorizeBaseController

_logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helper konfigurasi SSO berbasis module-level function
# ------------------------------------------------------------------
def _sso_param(key, default=False):
    return request.env['ir.config_parameter'].sudo().get_param(key, default)


def _sso_client_id():
    return _sso_param('mentorize.sso.client_id', 'local_mentorize')


def _sso_client_secret():
    return _sso_param('mentorize.sso.client_secret', False)


def _sso_redirect_uri():
    default_uri = request.httprequest.host_url.rstrip('/') + '/sso/callback'
    return _sso_param('mentorize.sso.redirect_uri', default_uri)


def _sso_post_logout_redirect():
    default_uri = request.httprequest.host_url.rstrip('/') + '/'
    return _sso_param('mentorize.sso.post_logout_redirect_uri', default_uri)


def _sso_authorize_url():
    return _sso_param('mentorize.sso.authorize_url', 'https://service.unisayogya.ac.id/sso/authorize.php')


def _sso_token_url():
    return _sso_param('mentorize.sso.token_url', 'https://service.unisayogya.ac.id/sso/token.php')


def _sso_logout_url():
    return _sso_param('mentorize.sso.logout_url', 'https://service.unisayogya.ac.id/sso/logout.php')


def _sso_verify_ssl():
    """Verifikasi SSL.

    Untuk development lokal kadang server SSO masih memerlukan verify=False.
    Untuk production, parameter ini sebaiknya true.
    """
    value = str(_sso_param('mentorize.sso.verify_ssl', 'false')).lower()
    return value in ('1', 'true', 'yes', 'y')


# ------------------------------------------------------------------
# Helper kecil
# ------------------------------------------------------------------
def _first_value(*values):
    for value in values:
        if value not in (None, False, ''):
            return str(value).strip()
    return ''


def _extract_claims_from_jwt(access_token):
    """Decode payload JWT tanpa validasi signature.

    Signature idealnya diverifikasi dengan JWKS jika SSO menyediakan public key.
    Untuk saat ini mengikuti implementasi SSO yang sudah berjalan di versi kanan.
    """
    try:
        parts = access_token.split('.')
        if len(parts) < 2:
            return {}
        payload64 = parts[1]
        payload64 += '=' * ((4 - len(payload64) % 4) % 4)
        payload_json = base64.urlsafe_b64decode(payload64.encode('utf-8'))
        return json.loads(payload_json)
    except Exception as exc:
        _logger.exception('Gagal decode JWT SSO: %s', exc)
        return {}


def _safe_redirect_after_login(controller=None, role=False):
    """Redirect setelah login tanpa wajib bergantung pada method self.

    Kalau method _redirect_after_login dari base tersedia, tetap dipakai agar alur
    profile setup existing tidak berubah. Kalau tidak tersedia, gunakan fallback aman.
    """
    try:
        if controller and hasattr(controller, '_redirect_after_login'):
            return controller._redirect_after_login()
    except Exception as exc:
        _logger.info('Fallback redirect_after_login dipakai: %s', exc)

    user = request.env.user
    role = role or getattr(user, 'mentorize_role', False)
    if role == 'alumni':
        return request.redirect('/alumni/dashboard')
    if role == 'admin':
        return request.redirect('/admin/dashboard')
    return request.redirect('/dashboard')


# ------------------------------------------------------------------
# Helper role dan profil SSO
# ------------------------------------------------------------------
def _resolve_role_from_sso(username, kwargs, token_data=None, claims=None):
    """Menentukan role Mentorize dari status akademik SSO.

    Aturan final yang disepakati:
    - kdstatus=A → mahasiswa aktif → role mahasiswa
    - kdstatus=L → mahasiswa lulus/alumni → role alumni
    - kdstatus selain A dan L → ditolak masuk Mentorize

    Field ``loginas`` tetap dibaca sebagai konteks, tetapi role final utama
    ditentukan oleh ``kdstatus`` agar mahasiswa lulus tidak keliru masuk
    sebagai mahasiswa aktif.
    """
    token_data = token_data or {}
    claims = claims or {}

    callback_role = _first_value(
        kwargs.get('role'),
        token_data.get('role'),
        token_data.get('loginas'),
        claims.get('role'),
        claims.get('loginas'),
    ).lower()
    loginas = _first_value(
        kwargs.get('loginas'),
        token_data.get('loginas'),
        claims.get('loginas'),
        callback_role,
    ).lower()
    kdstatus = _first_value(
        kwargs.get('kdstatus'),
        kwargs.get('status'),
        token_data.get('kdstatus'),
        token_data.get('status'),
        claims.get('kdstatus'),
        claims.get('status'),
    ).upper()

    _logger.info('Resolve role SSO: username=%s loginas=%s role=%s kdstatus=%s', username, loginas, callback_role, kdstatus)

    if kdstatus:
        if kdstatus == 'A':
            return 'mahasiswa'
        if kdstatus == 'L':
            return 'alumni'
        return False

    # Fallback hanya dipakai jika SSO tidak mengirim kdstatus sama sekali.
    # Jika user memang login sebagai alumni tanpa kdstatus, tetap boleh masuk alumni.
    if loginas == 'alumni' or callback_role == 'alumni':
        return 'alumni'

    return _resolve_role_from_database(username)


def _resolve_role_from_database(username):
    """Fallback cek database kampus jika schema SIMPTT tersedia.

    Hanya status A dan L yang diterima. Status lain atau status kosong tidak dipaksa.
    Query dibungkus savepoint agar jika tabel SIMPTT tidak ada, transaksi Odoo tidak aborted.
    """
    cr = request.env.cr

    try:
        with cr.savepoint():
            cr.execute("SELECT to_regclass(%s)", ['simptt.ak_mahasiswa'])
            table_exists = cr.fetchone()[0]

            if not table_exists:
                _logger.info('Tabel simptt.ak_mahasiswa tidak tersedia. Fallback role database dilewati.')
                return False

            cr.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'simptt'
                  AND table_name = 'ak_mahasiswa'
                  AND column_name IN ('kdstatus', 'status', 'status_mhs', 'statusmahasiswa')
            """)
            status_cols = [row[0] for row in cr.fetchall()]

            if not status_cols:
                return False

            select_status = ', '.join(status_cols)
            query = 'SELECT nim, %s FROM simptt.ak_mahasiswa WHERE nim = %%s LIMIT 1' % select_status
            cr.execute(query, [username])
            row = cr.dictfetchone()

            if not row:
                return False

            status_values = [str(row.get(col) or '').strip().upper() for col in status_cols]
            status_values = [val for val in status_values if val]

            if 'A' in status_values or 'AKTIF' in status_values:
                return 'mahasiswa'
            if 'L' in status_values or 'LULUS' in status_values:
                return 'alumni'
            return False

    except Exception as exc:
        _logger.info('Fallback database kampus tidak tersedia/diabaikan: %s', exc)
        return False


def _fetch_profile_from_database(username, role):
    """Ambil nama dari database kampus jika schema SIMPTT tersedia.

    Di lokal, schema/table simptt.ak_mahasiswa bisa saja tidak ada. Jangan biarkan
    error SQL membuat transaksi Odoo aborted. Kalau tidak ada, pakai NIM sebagai nama.
    """
    cr = request.env.cr
    default_profile = {
        'namalengkap': username,
        'email': username,
        'kdperson': None,
        'kdunitkerja': None,
    }

    try:
        with cr.savepoint():
            cr.execute("SELECT to_regclass(%s)", ['simptt.ak_mahasiswa'])
            ak_mahasiswa_exists = cr.fetchone()[0]

            cr.execute("SELECT to_regclass(%s)", ['simptt.pt_person'])
            pt_person_exists = cr.fetchone()[0]

            if not ak_mahasiswa_exists:
                _logger.info('Tabel simptt.ak_mahasiswa tidak tersedia. Profil SSO memakai fallback username.')
                return default_profile

            if pt_person_exists:
                cr.execute("""
                    SELECT pp.namalengkap, pp.kdperson, mhs.kdunitkerja
                    FROM simptt.ak_mahasiswa mhs
                    LEFT JOIN simptt.pt_person pp ON pp.kdperson = mhs.kdperson
                    WHERE mhs.nim = %s
                    LIMIT 1
                """, [username])
                row = cr.dictfetchone() or {}
                return {
                    'namalengkap': row.get('namalengkap') or username,
                    'email': username,
                    'kdperson': row.get('kdperson'),
                    'kdunitkerja': row.get('kdunitkerja'),
                }

            # Kalau ak_mahasiswa ada tapi pt_person tidak ada.
            cr.execute("""
                SELECT nim, kdperson, kdunitkerja
                FROM simptt.ak_mahasiswa
                WHERE nim = %s
                LIMIT 1
            """, [username])
            row = cr.dictfetchone() or {}
            return {
                'namalengkap': username,
                'email': username,
                'kdperson': row.get('kdperson'),
                'kdunitkerja': row.get('kdunitkerja'),
            }

    except Exception as exc:
        _logger.info('Profil kampus tidak tersedia/diabaikan: %s', exc)
        return default_profile


# ------------------------------------------------------------------
# Helper user dan session Odoo
# ------------------------------------------------------------------
def _sync_user_role_local(user, role):
    """Sinkronisasi group tanpa bergantung pada method base controller."""
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
            if portal_group and portal_group not in current_groups:
                commands.append((4, portal_group.id))
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

    except Exception as exc:
        _logger.info('Sinkronisasi group SSO memakai fallback: %s', exc)

    if commands:
        vals['groups_id'] = commands
    if vals:
        user.sudo().write(vals)
    return role


def _create_or_update_sso_user(username, role, profile):
    """Membuat atau memperbarui user Odoo dari data SSO.

    Prinsip penting setelah SSO aktif:
    - SSO hanya menjadi sumber autentikasi, role, dan status akademik.
    - Data profil yang sudah diisi user di Mentorize tidak boleh ditimpa lagi
      oleh fallback SSO seperti name=NIM atau email=NIM saat login ulang.
    - Alumni dari SSO kdstatus=L tetap otomatis dianggap valid secara sistem
      (is_verified=True), tetapi verifikasi manual admin tidak dipakai lagi di UI.

    Return: (user, error_message)
    """
    Users = request.env['res.users'].sudo().with_context(active_test=False)
    user = Users.search([('login', '=', username)], limit=1)

    if user and not user.active:
        message = user.mentorize_block_reason or 'Akun Anda sedang dinonaktifkan oleh admin Mentorize.'
        _logger.warning('SSO login ditolak karena user tidak aktif. username=%s reason=%s', username, message)
        return False, message

    profile_name = (profile.get('namalengkap') or username or '').strip()
    profile_email = (profile.get('email') or '').strip().lower()
    profile_email_valid = '@' in profile_email and '.' in profile_email.split('@')[-1]

    if user:
        vals = {
            'mentorize_role': role,
            'is_verified': True,
        }

        # Jangan timpa nama/email user yang sudah dilengkapi.
        current_name = (user.name or '').strip()
        current_email = (user.email or '').strip().lower()
        name_is_fallback = (not current_name) or current_name == username
        email_is_fallback = (not current_email) or current_email == username or '@' not in current_email

        if name_is_fallback:
            vals['name'] = profile_name or username
        if email_is_fallback and profile_email_valid:
            vals['email'] = profile_email

        if role == 'mahasiswa':
            if not user.nim:
                vals['nim'] = username
            # Jika user sebelumnya pernah login sebagai alumni karena status berubah, jangan paksa hapus data lama.
        else:
            if not user.kapa:
                vals['kapa'] = username
            if not user.nim:
                vals['nim'] = username

        user.write(vals)
    else:
        vals = {
            'name': profile_name or username,
            'login': username,
            # Kalau SSO belum memberi email valid, biarkan email berisi username dulu.
            # Profile gate akan memaksa user mengisi email notifikasi valid sebelum lanjut.
            'email': profile_email if profile_email_valid else username,
            'mentorize_role': role,
            'is_verified': True,
            'mentorize_notification_email': True,
        }
        if role == 'mahasiswa':
            vals.update({'nim': username})
        else:
            vals.update({'kapa': username, 'nim': username})
        user = Users.create(vals)

    _sync_user_role_local(user, role)

    if role == 'mahasiswa':
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not mahasiswa:
            request.env['mentorize.mahasiswa'].sudo().create({
                'user_id': user.id,
                'nim': user.nim or username,
                'jurusan': user.jurusan or '',
                'tujuan_karir': user.tujuan_karir or '',
                'bio': user.bio or '',
            })
        else:
            update_vals = {}
            if not mahasiswa.nim:
                update_vals['nim'] = user.nim or username
            if update_vals:
                mahasiswa.write(update_vals)
    else:
        alumni = request.env['mentorize.alumni'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not alumni:
            request.env['mentorize.alumni'].sudo().create({
                'user_id': user.id,
                'kapa': user.kapa or username,
                'is_verified': True,
                'availability': 'available',
            })
        else:
            update_vals = {'is_verified': True}
            if not alumni.kapa:
                update_vals['kapa'] = user.kapa or username
            alumni.write(update_vals)

    return user, False


def _authenticate_sso_user(user):
    """Membuat session Odoo untuk user SSO.

    Di beberapa instalasi Odoo 17, request.session.authenticate() bisa gagal
    untuk user hasil SSO walaupun token SSO sudah valid, biasanya karena
    kombinasi portal/internal group, password hash baru belum terbaca oleh
    proses autentikasi, atau user dibuat/diubah pada transaksi yang sama.

    Karena autentikasi utama sudah dilakukan oleh SSO, kita tetap coba cara
    standar Odoo lebih dulu. Jika gagal, baru pakai fallback session langsung
    dengan session_token agar request berikutnya tidak 403.
    """
    user = user.sudo()

    if not user or not user.exists():
        _logger.error('SSO session gagal: user tidak ditemukan.')
        return False

    if not user.active:
        _logger.warning('SSO session gagal: user %s tidak aktif.', user.login)
        return False

    # Pastikan perubahan user/group tersimpan sebelum sesi dibuat.
    try:
        request.env.cr.flush()
    except Exception:
        pass

    temp_password = secrets.token_urlsafe(32)
    try:
        user.write({'password': temp_password})
        request.env.cr.flush()

        uid = request.session.authenticate(request.db, user.login, temp_password)
        if uid:
            _logger.info('Session Odoo SSO berhasil dibuat via authenticate untuk user %s.', user.login)
            return uid
    except Exception as exc:
        _logger.exception('Authenticate standar SSO gagal untuk user %s, fallback session langsung dipakai: %s', user.login, exc)

    # Fallback aman: hanya dipakai setelah token SSO valid dan user berhasil dibuat/update.
    try:
        db_name = request.db or request.session.db
        request.session.db = db_name
        request.session.uid = user.id
        request.session.login = user.login

        # Odoo 17 memakai session_token untuk validasi session pada request berikutnya.
        try:
            session_token = user._compute_session_token(request.session.sid)
            request.session.session_token = session_token
        except Exception as token_exc:
            _logger.info('Tidak bisa membuat session_token eksplisit untuk SSO user %s: %s', user.login, token_exc)

        try:
            request.session.context = dict(request.env['res.users'].sudo().browse(user.id).context_get())
        except Exception:
            request.session.context = {}

        try:
            request.update_env(user=user.id)
        except Exception:
            pass

        _logger.info('Session Odoo SSO berhasil dibuat via fallback langsung untuk user %s.', user.login)
        return user.id

    except Exception as exc:
        _logger.exception('Fallback session langsung SSO tetap gagal untuk user %s: %s', user.login, exc)
        return False


def _log_activity_safe(controller, user, description='Login melalui SSO UNISA.'):
    try:
        if controller and hasattr(controller, '_log_activity'):
            controller._log_activity('login', description, 'res.users', user.id, user)
            return
    except Exception:
        pass

    try:
        request.env['mentorize.activity'].sudo().log(
            user=user,
            activity_type='login',
            description=description,
            related_model='res.users',
            related_id=user.id,
        )
    except Exception:
        pass


# ------------------------------------------------------------------
# Controller route SSO
# ------------------------------------------------------------------
class MentorizeSsoController(MentorizeBaseController):
    """Menangani login, callback, dan logout SSO UNISA."""

    @http.route('/sso/login', type='http', auth='public', website=True, csrf=False, sitemap=False)
    def sso_login(self, **kwargs):
        """Mulai proses login SSO dengan PKCE."""
        if not request.env.user._is_public():
            return _safe_redirect_after_login(self)

        client_id = _sso_client_id()
        redirect_uri = _sso_redirect_uri()

        # PKCE: simpan verifier di session, kirim challenge ke SSO.
        code_verifier = secrets.token_urlsafe(48)
        digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

        request.session['mentorize_sso_code_verifier'] = code_verifier
        request.session['mentorize_sso_redirect_uri'] = redirect_uri

        sso_url = (
            '%s?client_id=%s&redirect_uri=%s&response_type=code&scope=profile'
            '&code_challenge=%s&code_challenge_method=S256'
        ) % (
            _sso_authorize_url(),
            quote_plus(client_id),
            quote_plus(redirect_uri),
            quote_plus(code_challenge),
        )

        _logger.warning('=== SSO SAFE FINAL 2026-06-09 KEBACA ===')
        _logger.info('Mentorize SSO redirect URL: %s', sso_url)
        return request.redirect(sso_url, code=303, local=False)

    @http.route('/sso/callback', type='http', auth='public', website=True, csrf=False, sitemap=False)
    def sso_callback(self, **kwargs):
        """Callback resmi SSO. Menukar code menjadi token, lalu login ke Odoo."""
        _logger.warning('=== SSO SAFE FINAL CALLBACK 2026-06-09 KEBACA ===')
        return _handle_sso_callback(self, kwargs)


def _handle_sso_callback(controller, kwargs):
    """Memproses callback SSO dan membuat session Odoo."""
    _logger.info('=== Mentorize SSO Callback ===')
    _logger.info('Callback params: %s', kwargs)

    auth_code = kwargs.get('code')
    if not auth_code:
        return request.make_response('Kode SSO tidak ditemukan.', status=403)

    client_id = _sso_client_id()
    client_secret = _sso_client_secret()
    if not client_secret:
        return request.make_response(
            'Client secret SSO belum diatur. Isi System Parameters: mentorize.sso.client_secret',
            status=403,
        )

    redirect_uri = request.session.get('mentorize_sso_redirect_uri') or _sso_redirect_uri()
    code_verifier = request.session.get('mentorize_sso_code_verifier')

    try:
        resp = http_requests.post(
            _sso_token_url(),
            data={
                'grant_type': 'authorization_code',
                'code': auth_code,
                'client_id': client_id,
                'redirect_uri': redirect_uri,
                'client_secret': client_secret,
                'code_verifier': code_verifier,
            },
            timeout=20,
            verify=_sso_verify_ssl(),
        )
        _logger.info('SSO token status: %s', resp.status_code)
        _logger.info('SSO token response: %s', resp.text)
    except Exception as exc:
        _logger.exception('Gagal menghubungi server SSO: %s', exc)
        return request.make_response('Gagal menghubungi server SSO.', status=403)

    if resp.status_code != 200:
        return request.make_response('SSO gagal. Server SSO menolak pertukaran token.', status=403)

    try:
        data = resp.json()
    except Exception:
        return request.make_response('Response SSO tidak valid.', status=403)

    isallowed = data.get('isallowed')
    if isallowed is not None and str(isallowed).lower() in ('false', '0', 'no', 'n'):
        return request.make_response('Akun Anda tidak diizinkan masuk ke Mentorize oleh SSO.', status=403)

    access_token = data.get('access_token')
    if not access_token:
        return request.make_response('Access token SSO tidak ditemukan.', status=403)

    claims = _extract_claims_from_jwt(access_token)
    _logger.info('JWT Claims: %s', claims)

    username = claims.get('sub') or data.get('username') or data.get('nim') or kwargs.get('username') or kwargs.get('nim')
    if not username:
        return request.make_response('Username/NIM tidak ditemukan dari SSO.', status=403)
    username = str(username).strip()

    role = _resolve_role_from_sso(username, kwargs, data, claims)
    if not role:
        kdstatus_info = _first_value(kwargs.get('kdstatus'), data.get('kdstatus'), claims.get('kdstatus'), '-')
        _logger.warning('SSO login ditolak karena kdstatus belum didukung. username=%s kdstatus=%s data=%s kwargs=%s', username, kdstatus_info, data, kwargs)
        return request.make_response(
            'Status akademik Anda belum didukung untuk masuk ke Mentorize. '
            'Hanya mahasiswa aktif (A) dan alumni/lulus (L) yang dapat masuk. '
            'Silakan hubungi admin atau pihak kampus.',
            status=403,
        )

    profile = _fetch_profile_from_database(username, role)
    _logger.info('Role final SSO: %s | Profile: %s', role, profile)

    user, create_error = _create_or_update_sso_user(username, role, profile)
    if create_error:
        return request.make_response(create_error, status=403)
    if not user:
        return request.make_response('Gagal membuat atau memperbarui user SSO.', status=403)

    uid = _authenticate_sso_user(user)
    if not uid:
        return request.make_response('Gagal membuat session Odoo dari SSO.', status=403)

    try:
        request.update_env(user=uid)
    except Exception:
        pass

    request.session['login_method'] = 'sso'
    request.session['sso_username'] = username
    _log_activity_safe(controller, user, 'Login melalui SSO UNISA.')

    _logger.info('=== SSO Login Berhasil: %s (%s) ===', username, role)
    return _safe_redirect_after_login(controller, role=role)
