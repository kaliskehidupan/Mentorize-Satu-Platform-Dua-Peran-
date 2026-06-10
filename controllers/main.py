import base64
import json
from datetime import datetime, timedelta

from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import AccessDenied


class MentorizeController(http.Controller):
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

        if user.login == 'admin@mentorize.com':
            return 'admin'

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
            'is_admin_page': False,
        }

    def _verify_mahasiswa_identity(self, nim, name):
        """Hook untuk integrasi API NIM asli nanti. Saat ini sengaja dibuat lolos dulu."""
        return True, 'OK'

    def _verify_alumni_identity(self, kapa, name):
        """Hook untuk integrasi API KAPA asli nanti. Saat ini sengaja dibuat lolos dulu."""
        return True, 'OK'

    def _match_label(self, score):
        if score >= 85:
            return 'Sangat Cocok'
        if score >= 70:
            return 'Cocok'
        if score >= 50:
            return 'Cukup Cocok'
        if score > 0:
            return 'Perlu Dipertimbangkan'
        return 'Belum Ada Kecocokan'

    def _score_mentor(self, mahasiswa, mentor):
        """Hitung skor matchmaking 0-100 berdasarkan minat, skill, tujuan karir, availability, dan rating."""
        mahasiswa_minat = set(mahasiswa.minat_ids.ids)
        mahasiswa_skill = set(mahasiswa.skill_ids.ids)
        mentor_minat = set(mentor.minat_ids.ids)
        mentor_skill = set(mentor.skill_ids.ids)

        minat_match_ids = list(mahasiswa_minat.intersection(mentor_minat))
        skill_match_ids = list(mahasiswa_skill.intersection(mentor_skill))

        minat_base = max(len(mahasiswa_minat), 1)
        skill_base = max(len(mahasiswa_skill), 1)
        minat_score = min((len(minat_match_ids) / minat_base) * 30.0, 30.0)
        skill_score = min((len(skill_match_ids) / skill_base) * 40.0, 40.0)

        tujuan = (mahasiswa.tujuan_karir or '').lower()
        text_profile = ' '.join([
            mentor.pekerjaan or '', mentor.tempat_bekerja or '', mentor.deskripsi or '',
            ' '.join(mentor.minat_ids.mapped('name')), ' '.join(mentor.skill_ids.mapped('name')),
        ]).lower()
        keywords = [w.strip('.,;:-_/()[]{}') for w in tujuan.split() if len(w.strip('.,;:-_/()[]{}')) >= 4]
        matched_keywords = []
        for word in keywords[:12]:
            if word and word in text_profile and word not in matched_keywords:
                matched_keywords.append(word)
        career_score = min(len(matched_keywords) * 5.0, 15.0)

        availability_score = 10.0 if mentor.availability == 'available' else (5.0 if mentor.availability == 'busy' else 0.0)
        rating_score = min(float(mentor.rating or 0.0), 5.0)
        score = round(min(skill_score + minat_score + career_score + availability_score + rating_score, 100.0), 1)

        Skill = request.env['mentorize.skill'].sudo()
        Minat = request.env['mentorize.minat'].sudo()
        matched_skills = Skill.browse(skill_match_ids).mapped('name')
        matched_minat = Minat.browse(minat_match_ids).mapped('name')
        reasons = []
        if matched_skills:
            reasons.append('Skill cocok: ' + ', '.join(matched_skills[:3]))
        if matched_minat:
            reasons.append('Minat cocok: ' + ', '.join(matched_minat[:3]))
        if matched_keywords:
            reasons.append('Tujuan karir relevan: ' + ', '.join(matched_keywords[:3]))
        if mentor.availability == 'available':
            reasons.append('Mentor sedang tersedia')
        if not reasons:
            reasons.append('Lengkapi minat/skill agar skor lebih akurat')

        return score, reasons, self._match_label(score)

    def _rank_mentors(self, mahasiswa, mentors):
        ranked = []
        for mentor in mentors:
            score, reasons, label = self._score_mentor(mahasiswa, mentor)
            ranked.append({
                'mentor': mentor,
                'score': score,
                'reasons': reasons,
                'label': label,
            })
        ranked.sort(key=lambda item: (item['score'], item['mentor'].rating or 0.0, item['mentor'].id), reverse=True)
        return ranked

    def _mentor_match_context(self, ranked):
        return {
            'match_scores': {item['mentor'].id: item['score'] for item in ranked},
            'match_reasons': {item['mentor'].id: item['reasons'] for item in ranked},
            'match_labels': {item['mentor'].id: item['label'] for item in ranked},
        }

    def _recommend_mentors(self, mahasiswa, limit=6):
        Alumni = request.env['mentorize.alumni'].sudo()
        mentors = Alumni.search([
            ('user_id', '!=', False),
            ('user_id.active', '=', True),
            ('availability', '!=', 'offline'),
            ('is_verified', '=', True),
        ])

        ranked = self._rank_mentors(mahasiswa, mentors)
        top_ranked = ranked[:limit]

        if top_ranked:
            Match = request.env['mentorize.matchmaking'].sudo()
            for item in top_ranked:
                mentor = item['mentor']
                existing = Match.search([('mahasiswa_id', '=', mahasiswa.id), ('alumni_id', '=', mentor.id), ('request_id', '=', False)], limit=1)
                vals = {
                    'mahasiswa_id': mahasiswa.id,
                    'alumni_id': mentor.id,
                    'score': item['score'],
                    'alasan': '; '.join(item['reasons']),
                    'status': 'recommended',
                }
                if existing:
                    existing.write(vals)
                else:
                    Match.create(vals)

        return [item['mentor'] for item in top_ranked]

    def _room_allowed(self, room):
        user = request.env.user
        return room and (
            room.mahasiswa_user_id.id == user.id
            or room.alumni_user_id.id == user.id
            or user.mentorize_role == 'admin'
        )


    def _is_admin(self):
        user = request.env.user
        if user._is_public():
            return False
        if user.mentorize_role == 'admin':
            return True
        group = request.env.ref('mentorize.group_mentorize_admin', raise_if_not_found=False)
        return bool(group and group in user.sudo().groups_id)

    def _require_admin(self):
        if not self._is_admin():
            return request.redirect('/admin/login?error=Akses admin diperlukan')
        return False

    def _log_activity(self, activity_type, description, related_model=False, related_id=False, user=False):
        try:
            request.env['mentorize.activity'].sudo().log(
                user=user or request.env.user,
                activity_type=activity_type,
                description=description,
                related_model=related_model,
                related_id=related_id,
            )
        except Exception:
            pass

    def _room_chat_open(self, room):
        if not room or not room.exists():
            return False
        if room.status != 'active':
            return False
        if room.request_id and room.request_id.status != 'approved':
            return False
        session = room.session_id
        if session and session.status in ['completed', 'cancelled', 'stopped', 'stop_requested']:
            return False
        return True

    def _other_user_for_room(self, room):
        if not room:
            return request.env['res.users'].sudo().browse([])
        return room.alumni_user_id if room.mahasiswa_user_id.id == request.env.user.id else room.mahasiswa_user_id

    def _admin_base_values(self, active='dashboard'):
        values = self._layout_values(active)
        values.update({'is_admin_page': True})
        return values

    # ---------- admin login ----------
    @http.route(['/admin/login', '/mentorize/admin/login'], type='http', auth='public', website=True, sitemap=False)
    def admin_login(self, **kwargs):
        if not request.env.user._is_public() and self._infer_user_role(request.env.user) == 'admin':
            return request.redirect('/admin/dashboard')
        return request.render('mentorize.page_admin_login', {
            'error': kwargs.get('error') or False,
            'old_email': kwargs.get('email') or '',
        })

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
                # 🔥 FORCE ADMIN OVERRIDE UNTUK AKUN INI
                if user.login == 'admin@mentorize.com':
                    role = 'admin'
                    is_admin = True
                if not is_admin:
                    request.session.logout(keep_db=True)
                    return render_error('Akun ini tidak memiliki akses Admin Mentorize.')
                self._sync_user_role(user, 'admin')
                # 🔥 jangan ganggu group saat login admin khusus
                if user.login != 'admin@mentorize.com':
                    self._sync_user_role(user, 'admin')
                try:
                    request.update_env(user=uid)
                except Exception:
                    pass
                self._log_activity('login', 'Admin login ke panel Mentorize.', 'res.users', user.id, user)
                return request.redirect('/admin/dashboard')
        except AccessDenied:
            pass
        except Exception:
            pass

        return render_error('Email atau password admin salah.')


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
                'is_verified': False,
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
                    'is_verified': False,
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

        recommended = self._recommend_mentors(mahasiswa, limit=3)
        ranked_recommended = self._rank_mentors(mahasiswa, recommended)
        match_context = self._mentor_match_context(ranked_recommended)

        values = self._layout_values('dashboard')
        values.update({
            'mahasiswa': mahasiswa,
            'recommended_mentors': recommended,
            'match_scores': match_context['match_scores'],
            'match_reasons': match_context['match_reasons'],
            'match_labels': match_context['match_labels'],
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

        req_ranked = []
        for req in requests_list:
            score, reasons, label = self._score_mentor(req.mahasiswa_id, alumni)
            req_ranked.append({'request': req, 'score': score, 'reasons': reasons, 'label': label})
        req_match_scores = {item['request'].id: item['score'] for item in req_ranked}
        req_match_labels = {item['request'].id: item['label'] for item in req_ranked}
        req_match_reasons = {item['request'].id: item['reasons'] for item in req_ranked}

        values = self._layout_values('dashboard')
        values.update({
            'alumni': alumni,
            'request_match_scores': req_match_scores,
            'request_match_labels': req_match_labels,
            'request_match_reasons': req_match_reasons,
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

    @http.route(['/admin/dashboard', '/mentorize/admin/dashboard'], type='http', auth='user', website=True, sitemap=False)
    def admin_dashboard(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect

        Mahasiswa = request.env['mentorize.mahasiswa'].sudo()
        Alumni = request.env['mentorize.alumni'].sudo()
        Request = request.env['mentorize.request'].sudo()
        Session = request.env['mentorize.session'].sudo()
        Feedback = request.env['mentorize.feedback'].sudo()
        Report = request.env['mentorize.pelanggaran'].sudo()
        Activity = request.env['mentorize.activity'].sudo()

        total_mahasiswa = Mahasiswa.search_count([])
        total_alumni = Alumni.search_count([])
        total_requests = Request.search_count([])
        total_sessions = Session.search_count([])
        pending_alumni = Alumni.search_count([('is_verified', '=', False)])
        active_reports = Report.search_count([('status', 'in', ['baru', 'diproses'])])

        request_chart = {
            'pending': Request.search_count([('status', '=', 'pending')]),
            'approved': Request.search_count([('status', '=', 'approved')]),
            'rejected': Request.search_count([('status', '=', 'rejected')]),
            'done': Request.search_count([('status', '=', 'done')]),
        }
        session_chart = {
            'scheduled': Session.search_count([('status', 'in', ['scheduled', 'active'])]),
            'end_requested': Session.search_count([('status', '=', 'end_requested')]),
            'completed': Session.search_count([('status', '=', 'completed')]),
            'stopped': Session.search_count([('status', 'in', ['stopped', 'cancelled'])]),
        }
        report_chart = {
            'baru': Report.search_count([('status', '=', 'baru')]),
            'diproses': Report.search_count([('status', '=', 'diproses')]),
            'selesai': Report.search_count([('status', '=', 'selesai')]),
            'ditolak': Report.search_count([('status', '=', 'ditolak')]),
        }

        skills = request.env['mentorize.skill'].sudo().search([])
        skill_chart = []
        for skill in skills:
            count = Mahasiswa.search_count([('skill_ids', 'in', [skill.id])]) + Alumni.search_count([('skill_ids', 'in', [skill.id])])
            if count:
                skill_chart.append({'name': skill.name, 'count': count})
        skill_chart = sorted(skill_chart, key=lambda x: x['count'], reverse=True)[:6]
        max_skill = max([x['count'] for x in skill_chart] or [1])

        top_alumni = Alumni.search([('user_id.active', '=', True)], limit=6)
        top_alumni = sorted(top_alumni, key=lambda a: (Session.search_count([('alumni_id', '=', a.id), ('status', '=', 'completed')]), a.rating), reverse=True)[:5]

        values = self._admin_base_values('dashboard')
        values.update({
            'total_mahasiswa': total_mahasiswa,
            'total_alumni': total_alumni,
            'total_requests': total_requests,
            'total_sessions': total_sessions,
            'pending_alumni': pending_alumni,
            'active_reports': active_reports,
            'request_chart': request_chart,
            'session_chart': session_chart,
            'report_chart': report_chart,
            'skill_chart': skill_chart,
            'max_skill': max_skill,
            'top_alumni': top_alumni,
            'recent_activities': Activity.search([], order='timestamp desc', limit=8),
            'recent_reports': Report.search([], order='create_date desc', limit=5),
            'avg_rating': round(sum(Feedback.search([]).mapped('rating')) / max(Feedback.search_count([]), 1), 1) if Feedback.search_count([]) else 0,
            'request_total_chart': max(sum(request_chart.values()), 1),
            'session_total_chart': max(sum(session_chart.values()), 1),
            'report_total_chart': max(sum(report_chart.values()), 1),
            'user_total_chart': max(total_mahasiswa + total_alumni, 1),
            'user_mahasiswa_pct': ((total_mahasiswa * 100.0) / max(total_mahasiswa + total_alumni, 1)),
        })
        return request.render('mentorize.dashboard_admin', values)

    @http.route(['/admin/skills'], type='http', auth='user', website=True, sitemap=False)
    def admin_skills(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect

        search = kwargs.get('search', '')
        selected_skill = kwargs.get('skill_id', '')
        selected_minat = kwargs.get('minat_id', '')

        skills = request.env['mentorize.skill'].sudo().search([])
        minats = request.env['mentorize.minat'].sudo().search([])

        mahasiswa_domain = []
        alumni_domain = []

        # FILTER SKILL
        if selected_skill:
            mahasiswa_domain.append(('skill_ids', 'in', int(selected_skill)))
            alumni_domain.append(('skill_ids', 'in', int(selected_skill)))

        # FILTER MINAT
        if selected_minat:
            mahasiswa_domain.append(('minat_ids', 'in', int(selected_minat)))
            alumni_domain.append(('minat_ids', 'in', int(selected_minat)))

        # SEARCH USER
        if search:
            mahasiswa_domain.append(('name', 'ilike', search))
            alumni_domain.append(('name', 'ilike', search))

        mahasiswa_users = request.env['mentorize.mahasiswa'].sudo().search(mahasiswa_domain)
        alumni_users = request.env['mentorize.alumni'].sudo().search(alumni_domain)

        # HITUNG USER PER SKILL
        skill_counts = {}

        for skill in skills:
            skill_counts[skill.id] = (
                request.env['mentorize.mahasiswa'].sudo().search_count([
                    ('skill_ids', 'in', skill.id)
                ]) +
                request.env['mentorize.alumni'].sudo().search_count([
                    ('skill_ids', 'in', skill.id)
                ])
            )

        # HITUNG USER PER MINAT
        minat_counts = {}

        for minat in minats:
            minat_counts[minat.id] = (
                request.env['mentorize.mahasiswa'].sudo().search_count([
                    ('minat_ids', 'in', minat.id)
                ]) +
                request.env['mentorize.alumni'].sudo().search_count([
                    ('minat_ids', 'in', minat.id)
                ])
            )

        values = self._admin_base_values('skills')

        values.update({
            'skills': skills,
            'minats': minats,
            'mahasiswa_users': mahasiswa_users,
            'alumni_users': alumni_users,
            'selected_skill': selected_skill,
            'selected_minat': selected_minat,
            'search': search,
            'skill_counts': skill_counts,
            'minat_counts': minat_counts,
            'skill_users': request.env['mentorize.mahasiswa'].sudo().search_count([
                ('skill_ids', '!=', False)
            ]),
            'minat_users': request.env['mentorize.mahasiswa'].sudo().search_count([
                ('minat_ids', '!=', False)
            ]),
        })

        return request.render('mentorize.admin_skills', values)

    @http.route(['/admin/users', '/mentorize/admin/users'], type='http', auth='user', website=True, sitemap=False)
    def admin_users(self, search='', role='', **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect

        domain = [('mentorize_role', '!=', False)]

        if search:
            domain += ['|', ('name', 'ilike', search), ('login', 'ilike', search)]

        if role in ['mahasiswa', 'alumni', 'admin']:
            domain.append(('mentorize_role', '=', role))

        users = request.env['res.users'].sudo().with_context(active_test=False).search(
            domain,
            order='create_date desc'
        )

        active_menu = 'verification' if role == 'alumni' else 'users'

        values = self._admin_base_values(active_menu)

        values.update({
            'users': users,
            'search': search,
            'selected_role': role,
            'total_users': len(users),
            'total_active': len(users.filtered(lambda u: u.active)),
            'total_suspend': len(users.filtered(lambda u: not u.active)),
        })

        return request.render('mentorize.admin_users', values)

    @http.route(['/admin/user/<int:user_id>/detail', '/mentorize/admin/user/<int:user_id>/detail'], type='http', auth='user', website=True, sitemap=False)
    def admin_user_detail(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        user_rec = request.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        if not user_rec.exists():
            return request.redirect('/admin/users')
        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([('user_id', '=', user_rec.id)], limit=1)
        alumni = request.env['mentorize.alumni'].sudo().search([('user_id', '=', user_rec.id)], limit=1)
        sessions = request.env['mentorize.session'].sudo().search(['|', ('mahasiswa_id.user_id', '=', user_rec.id), ('alumni_id.user_id', '=', user_rec.id)], order='tanggal_mentoring desc', limit=20)
        reports = request.env['mentorize.pelanggaran'].sudo().search(['|', ('pelapor_id', '=', user_rec.id), ('dilaporkan_id', '=', user_rec.id)], order='create_date desc', limit=20)
        values = self._admin_base_values('users')
        values.update({'target_user': user_rec, 'mahasiswa': mahasiswa, 'alumni': alumni, 'sessions': sessions, 'reports': reports})
        return request.render('mentorize.admin_user_detail', values)

    @http.route(['/admin/user/<int:user_id>/verify', '/mentorize/admin/user/verify/<int:user_id>'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_verify_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        user_rec = request.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        alumni = request.env['mentorize.alumni'].sudo().search([('user_id', '=', user_rec.id)], limit=1)
        if user_rec.exists():
            user_rec.write({'is_verified': True, 'mentorize_verified_at': fields.Datetime.now(), 'mentorize_verified_by': request.env.user.id})
            if alumni:
                alumni.write({'is_verified': True})
            self._log_activity('admin', 'Admin memverifikasi akun %s' % user_rec.name, 'res.users', user_rec.id)
            request.env['mentorize.notification'].sudo().create_notification(user_rec, 'Akun diverifikasi', 'Akun Mentorize kamu sudah diverifikasi admin.', 'info', '/dashboard')
        return request.redirect(kwargs.get('next') or '/admin/users')

    @http.route(['/admin/user/<int:user_id>/unverify'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_unverify_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        user_rec = request.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        alumni = request.env['mentorize.alumni'].sudo().search([('user_id', '=', user_rec.id)], limit=1)
        if user_rec.exists():
            user_rec.write({'is_verified': False})
            if alumni:
                alumni.write({'is_verified': False})
            self._log_activity('admin', 'Admin membatalkan verifikasi akun %s' % user_rec.name, 'res.users', user_rec.id)
        return request.redirect(kwargs.get('next') or '/admin/users')

    @http.route(['/admin/user/<int:user_id>/suspend', '/mentorize/admin/user/suspend/<int:user_id>'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_suspend_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        user_rec = request.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        reason = kwargs.get('reason') or 'Akun dinonaktifkan oleh admin Mentorize.'
        if user_rec.exists() and user_rec.id != request.env.user.id:
            user_rec.write({'active': False, 'mentorize_block_reason': reason})
            self._log_activity('admin', 'Admin menonaktifkan akun %s. Alasan: %s' % (user_rec.name, reason), 'res.users', user_rec.id)
        return request.redirect(kwargs.get('next') or '/admin/users')

    @http.route(['/admin/user/<int:user_id>/activate', '/mentorize/admin/user/activate/<int:user_id>'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_activate_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        user_rec = request.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        if user_rec.exists():
            user_rec.write({'active': True, 'mentorize_block_reason': False})
            self._log_activity('admin', 'Admin mengaktifkan kembali akun %s' % user_rec.name, 'res.users', user_rec.id)
        return request.redirect(kwargs.get('next') or '/admin/users')

    @http.route(['/admin/mentoring', '/mentorize/admin/mentoring'], type='http', auth='user', website=True, sitemap=False)
    def admin_mentoring(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        values = self._admin_base_values('mentoring')
        values.update({
            'requests_data': request.env['mentorize.request'].sudo().search([], order='create_date desc', limit=80),
            'sessions': request.env['mentorize.session'].sudo().search([], order='tanggal_mentoring desc', limit=80),
            'matchmakings': request.env['mentorize.matchmaking'].sudo().search([], order='create_date desc', limit=80),
        })
        return request.render('mentorize.admin_mentoring', values)

    @http.route(['/admin/feedback', '/mentorize/admin/feedback'], type='http', auth='user', website=True, sitemap=False)
    def admin_feedback(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        feedbacks = request.env['mentorize.feedback'].sudo().search([], order='create_date desc')
        values = self._admin_base_values('feedback')
        values.update({'feedbacks': feedbacks})
        return request.render('mentorize.admin_feedback', values)

    @http.route(['/admin/reports', '/admin/pelanggaran', '/mentorize/admin/pelanggaran'], type='http', auth='user', website=True, sitemap=False)
    def admin_reports(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        reports = request.env['mentorize.pelanggaran'].sudo().search([], order='create_date desc')
        values = self._admin_base_values('reports')
        values.update({
            'reports': reports,
            'total': len(reports),
            'baru': len(reports.filtered(lambda r: r.status == 'baru')),
            'diproses': len(reports.filtered(lambda r: r.status == 'diproses')),
            'selesai': len(reports.filtered(lambda r: r.status == 'selesai')),
        })
        return request.render('mentorize.admin_reports', values)

    @http.route('/admin/report/<int:report_id>/update', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def admin_report_update(self, report_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        report = request.env['mentorize.pelanggaran'].sudo().browse(report_id)
        if report.exists():
            status = kwargs.get('status') if kwargs.get('status') in ['baru', 'diproses', 'selesai', 'ditolak'] else report.status
            action = kwargs.get('action') if kwargs.get('action') in ['none', 'warning', 'disabled', 'ignored'] else report.action
            vals = {
                'status': status,
                'action': action,
                'admin_note': kwargs.get('admin_note') or report.admin_note,
                'processed_by': request.env.user.id,
            }
            if status in ['selesai', 'ditolak']:
                vals['resolved_at'] = fields.Datetime.now()
            report.write(vals)
            if action == 'disabled' and report.dilaporkan_id:
                report.dilaporkan_id.sudo().write({'active': False, 'mentorize_block_reason': report.admin_note or report.judul})
            request.env['mentorize.notification'].sudo().create_notification(report.pelapor_id, 'Update laporan', 'Laporan "%s" berstatus %s.' % (report.judul, dict(report._fields['status'].selection).get(report.status, report.status)), 'report_update', '/reports')
            self._log_activity('admin', 'Admin memproses laporan %s' % report.judul, 'mentorize.pelanggaran', report.id)
        return request.redirect('/admin/reports')

    @http.route(['/admin/activities', '/mentorize/admin/aktivitas'], type='http', auth='user', website=True, sitemap=False)
    def admin_activities(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        values = self._admin_base_values('activities')
        values.update({'activities': request.env['mentorize.activity'].sudo().search([], order='timestamp desc', limit=120)})
        return request.render('mentorize.admin_activities', values)

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
        auto_match = kwargs.get('match') == '1' or not query
        Alumni = request.env['mentorize.alumni'].sudo()

        if query:
            base_mentors = Alumni.search([
                ('user_id.active', '=', True),
                ('is_verified', '=', True),
                ('availability', '!=', 'offline'),
                '|', '|', '|', '|',
                ('user_id.name', 'ilike', query),
                ('pekerjaan', 'ilike', query),
                ('deskripsi', 'ilike', query),
                ('skill_ids.name', 'ilike', query),
                ('minat_ids.name', 'ilike', query),
            ])
        else:
            base_mentors = Alumni.search([
                ('user_id.active', '=', True),
                ('is_verified', '=', True),
                ('availability', '!=', 'offline'),
            ])

        ranked = self._rank_mentors(mahasiswa, base_mentors)
        mentors = [item['mentor'] for item in ranked] if auto_match or query else self._recommend_mentors(mahasiswa, limit=30)
        match_context = self._mentor_match_context(ranked)

        values = self._layout_values('mentors')
        values.update({
            'mahasiswa': mahasiswa,
            'mentors': mentors,
            'q': query,
            'match_active': auto_match,
            'match_scores': match_context['match_scores'],
            'match_reasons': match_context['match_reasons'],
            'match_labels': match_context['match_labels'],
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

        if not alumni.user_id.active or not alumni.is_verified or alumni.availability == 'offline':
            return request.redirect('/mentors?error=Mentor belum terverifikasi atau sedang tidak tersedia')

        req = request.env['mentorize.request'].sudo().create({
            'mahasiswa_id': mahasiswa.id,
            'alumni_id': alumni.id,
            'topik': topik,
            'deskripsi': deskripsi,
            'requested_datetime': requested_dt,
            'status': 'pending',
        })

        match = request.env['mentorize.matchmaking'].sudo().search([
            ('mahasiswa_id', '=', mahasiswa.id), ('alumni_id', '=', alumni.id), ('request_id', '=', False)
        ], limit=1)
        if match:
            match.write({'request_id': req.id, 'status': 'requested'})
        else:
            request.env['mentorize.matchmaking'].sudo().create({
                'mahasiswa_id': mahasiswa.id,
                'alumni_id': alumni.id,
                'request_id': req.id,
                'score': 0,
                'alasan': 'Request dibuat langsung oleh mahasiswa.',
                'status': 'requested',
            })

        request.env['mentorize.notification'].sudo().create_notification(
            alumni.user_id,
            'Request mentoring baru',
            '%s mengajukan mentoring tentang %s.' % (mahasiswa.name, topik),
            notif_type='request_new',
            url='/alumni/dashboard',
        )
        self._log_activity('request', 'Mahasiswa mengajukan request mentoring ke %s: %s' % (alumni.name, topik), 'mentorize.request', req.id, mahasiswa.user_id)

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

        other_user = self._other_user_for_room(selected_room) if selected_room else False
        values = self._layout_values('chat')
        values.update({
            'rooms': rooms,
            'selected_room': selected_room,
            'other_user': other_user,
            'can_chat': self._room_chat_open(selected_room) if selected_room else False,
            'current_role': self._infer_user_role(user),
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
            return self._json({'success': False, 'error': 'Room tidak valid'}, status=403)

        if not self._room_chat_open(room):
            return self._json({'success': False, 'error': 'Chat sudah terkunci atau request belum disetujui'}, status=403)

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
        self._log_activity('chat', 'Mengirim pesan di room mentoring %s' % room.id, 'mentorize.roomchat', room.id)

        return self._json({'success': True, 'message_id': msg.id})

    # ---------- ending session, summary, history ----------
    @http.route('/session/<int:session_id>/finish', type='http', auth='user', website=True, sitemap=False)
    def finish_session_form(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists() or not mahasiswa or session.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/dashboard')
        if session.status in ['completed', 'stopped', 'cancelled']:
            return request.redirect('/history/%s' % session.id)
        values = self._layout_values('history')
        values.update({'session': session, 'error': kwargs.get('error')})
        return request.render('mentorize.page_session_finish', values)

    @http.route('/session/<int:session_id>/end/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def request_end_session(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and mahasiswa and session.mahasiswa_id.id == mahasiswa.id:
            rating = int(kwargs.get('completion_rating') or kwargs.get('rating') or 5)
            rating = max(1, min(rating, 5))
            session.write({
                'status': 'end_requested',
                'end_request_note': kwargs.get('completion_summary') or kwargs.get('note') or '',
                'end_requested_at': fields.Datetime.now(),
                'completion_requested_by': request.env.user.id,
                'completion_title': kwargs.get('completion_title') or session.topik,
                'completion_method': kwargs.get('completion_method') or session.mode,
                'completion_summary': kwargs.get('completion_summary') or '',
                'material_discussed': kwargs.get('material_discussed') or '',
                'mentoring_result': kwargs.get('mentoring_result') or '',
                'follow_up_note': kwargs.get('follow_up_note') or '',
                'student_obstacle': kwargs.get('student_obstacle') or '',
                'completion_feedback': kwargs.get('completion_feedback') or '',
                'completion_rating': rating,
                'summary_topic': kwargs.get('completion_title') or session.topik,
                'summary_learnings': kwargs.get('mentoring_result') or kwargs.get('completion_summary') or '',
                'summary_advice': kwargs.get('follow_up_note') or '',
                'summary_next_steps': kwargs.get('follow_up_note') or '',
                'summary_notes': kwargs.get('student_obstacle') or '',
            })

            request.env['mentorize.notification'].sudo().create_notification(
                session.alumni_id.user_id,
                'Pengajuan akhir sesi',
                '%s mengajukan sesi mentoring untuk diselesaikan dan mengirim laporan hasil mentoring.' % mahasiswa.name,
                notif_type='session_end_requested',
                url='/alumni/dashboard',
            )
            self._log_activity('session', 'Mahasiswa mengajukan selesai mentoring: %s' % (session.topik or ''), 'mentorize.session', session.id, mahasiswa.user_id)

        return request.redirect('/dashboard')

    @http.route('/session/<int:session_id>/end/approve', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_end_session(self, session_id, **kwargs):
        alumni = self._current_alumni()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and alumni and session.alumni_id.id == alumni.id:
            session.write({
                'status': 'completed',
                'completed_at': fields.Datetime.now(),
                'completion_approved_by': request.env.user.id,
                'summary_saved': True,
            })

            session.request_id.write({'status': 'done'})

            if session.request_id.room_chat_id:
                session.request_id.room_chat_id.write({
                    'status': 'closed',
                    'closed_reason': 'Sesi mentoring selesai',
                    'closed_at': fields.Datetime.now(),
                })

            if not session.feedback_id:
                feedback = request.env['mentorize.feedback'].sudo().create({
                    'session_id': session.id,
                    'alumni_id': session.alumni_id.id,
                    'mahasiswa_id': session.mahasiswa_id.id,
                    'rating': session.completion_rating or 5,
                    'komentar': session.completion_feedback or session.completion_summary or '',
                })
                session.feedback_id = feedback.id

            request.env['mentorize.laporan'].sudo().create({
                'session_id': session.id,
                'mahasiswa_id': session.mahasiswa_id.id,
                'alumni_id': session.alumni_id.id,
                'judul': session.completion_title or session.topik or 'Laporan mentoring',
                'ringkasan': session.completion_summary or session.mentoring_result or '',
                'status': 'pending',
            })

            request.env['mentorize.notification'].sudo().create_notification(
                session.mahasiswa_id.user_id,
                'Sesi mentoring selesai',
                'Sesi mentoring kamu telah disetujui selesai. Laporan sudah masuk ke riwayat.',
                notif_type='session_completed',
                url='/history/%s' % session.id,
            )
            self._log_activity('session', 'Alumni menyetujui selesai mentoring: %s' % (session.topik or ''), 'mentorize.session', session.id, alumni.user_id)

        return request.redirect('/alumni/dashboard')

    @http.route('/session/<int:session_id>/end/reject', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def reject_end_session(self, session_id, **kwargs):
        alumni = self._current_alumni()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and alumni and session.alumni_id.id == alumni.id:
            session.write({'status': 'active'})

            request.env['mentorize.notification'].sudo().create_notification(
                session.mahasiswa_id.user_id,
                'Pengajuan akhir sesi belum disetujui',
                'Mentor merasa sesi masih perlu dilanjutkan.',
                notif_type='info',
                url='/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''),
            )

        return request.redirect('/alumni/dashboard')

    @http.route('/session/<int:session_id>/stop/request', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def request_stop_session(self, session_id, **kwargs):
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/chat')
        user = request.env.user
        allowed = user.id in [session.mahasiswa_id.user_id.id, session.alumni_id.user_id.id]
        if allowed and session.status not in ['completed', 'stopped', 'cancelled']:
            reason = kwargs.get('stop_reason') or 'Pengajuan berhenti mentoring.'
            session.write({
                'status': 'stop_requested',
                'stop_requested_by': user.id,
                'stop_reason': reason,
                'stop_requested_at': fields.Datetime.now(),
            })
            target = session.alumni_id.user_id if user.id == session.mahasiswa_id.user_id.id else session.mahasiswa_id.user_id
            request.env['mentorize.notification'].sudo().create_notification(target, 'Pengajuan berhenti mentoring', '%s mengajukan penghentian mentoring.' % user.name, 'session_stop_requested', '/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
            self._log_activity('session', 'Pengajuan berhenti mentoring: %s' % reason, 'mentorize.session', session.id)
        return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

    @http.route('/session/<int:session_id>/stop/approve', type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def approve_stop_session(self, session_id, **kwargs):
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/chat')
        user = request.env.user
        allowed = self._is_admin() or user.id in [session.mahasiswa_id.user_id.id, session.alumni_id.user_id.id]
        if allowed and session.status == 'stop_requested':
            session.write({
                'status': 'stopped',
                'stopped_at': fields.Datetime.now(),
                'stop_approved_by': user.id,
            })
            session.request_id.write({'status': 'done'})
            if session.request_id.room_chat_id:
                session.request_id.room_chat_id.write({
                    'status': 'closed',
                    'closed_reason': 'Mentoring dihentikan',
                    'closed_at': fields.Datetime.now(),
                })
            for target in [session.mahasiswa_id.user_id, session.alumni_id.user_id]:
                request.env['mentorize.notification'].sudo().create_notification(target, 'Mentoring dihentikan', 'Mentoring "%s" sudah dihentikan dan chat dikunci.' % (session.topik or ''), 'session_stopped', '/history/%s' % session.id)
            self._log_activity('session', 'Mentoring dihentikan: %s' % (session.stop_reason or ''), 'mentorize.session', session.id)
        return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

    @http.route('/session/<int:session_id>/reschedule', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def reschedule_session(self, session_id, **kwargs):
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/chat')
        user = request.env.user
        allowed = user.id in [session.mahasiswa_id.user_id.id, session.alumni_id.user_id.id]
        date_str = kwargs.get('tanggal_mentoring') or ''
        try:
            new_dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except Exception:
            return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
        if allowed and session.status not in ['completed', 'stopped', 'cancelled']:
            session.write({
                'tanggal_mentoring': new_dt,
                'status': 'scheduled',
                'reschedule_reason': kwargs.get('reschedule_reason') or '',
                'reschedule_requested_at': fields.Datetime.now(),
            })
            target = session.alumni_id.user_id if user.id == session.mahasiswa_id.user_id.id else session.mahasiswa_id.user_id
            request.env['mentorize.notification'].sudo().create_notification(target, 'Jadwal mentoring diubah', 'Jadwal mentoring "%s" diperbarui.' % (session.topik or ''), 'reschedule', '/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))
            self._log_activity('session', 'Reschedule mentoring: %s' % (session.topik or ''), 'mentorize.session', session.id)
        return request.redirect('/chat?room_id=%s' % (session.request_id.room_chat_id.id if session.request_id.room_chat_id else ''))

    @http.route('/summary/<int:session_id>', type='http', auth='user', website=True, sitemap=False)
    def summary(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if not session.exists() or not mahasiswa or session.mahasiswa_id.id != mahasiswa.id:
            return request.redirect('/dashboard')

        values = self._layout_values('history')
        values.update({'session': session, 'success': kwargs.get('success')})
        return request.render('mentorize.page_summary', values)

    @http.route('/summary/<int:session_id>/save', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def summary_save(self, session_id, **kwargs):
        mahasiswa = self._current_mahasiswa()
        session = request.env['mentorize.session'].sudo().browse(session_id)

        if session.exists() and mahasiswa and session.mahasiswa_id.id == mahasiswa.id:
            session.write({
                'summary_saved': True,
                'summary_topic': kwargs.get('summary_topic') or session.summary_topic or session.topik,
                'summary_learnings': kwargs.get('summary_learnings') or session.summary_learnings or '',
                'summary_advice': kwargs.get('summary_advice') or session.summary_advice or '',
                'summary_next_steps': kwargs.get('summary_next_steps') or session.summary_next_steps or '',
                'summary_notes': kwargs.get('summary_notes') or session.summary_notes or '',
            })
            rating = int(kwargs.get('rating') or session.completion_rating or 5)
            komentar = kwargs.get('komentar') or session.completion_feedback or ''
            if session.feedback_id:
                session.feedback_id.write({'rating': rating, 'komentar': komentar})
            else:
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
        role = self._infer_user_role(request.env.user)
        domain = [('status', 'in', ['completed', 'stopped', 'cancelled'])]
        if role == 'alumni':
            alumni = self._current_alumni()
            if not alumni:
                return request.redirect('/alumni/dashboard')
            domain.append(('alumni_id', '=', alumni.id))
        else:
            mahasiswa = self._current_mahasiswa()
            if not mahasiswa:
                return request.redirect('/dashboard')
            domain.append(('mahasiswa_id', '=', mahasiswa.id))
        sessions = request.env['mentorize.session'].sudo().search(domain, order='completed_at desc, stopped_at desc, tanggal_mentoring desc')
        values = self._layout_values('history')
        values.update({'sessions': sessions, 'history_role': role})
        return request.render('mentorize.page_history', values)

    @http.route('/history/<int:session_id>', type='http', auth='user', website=True, sitemap=False)
    def history_detail(self, session_id, **kwargs):
        role = self._infer_user_role(request.env.user)
        session = request.env['mentorize.session'].sudo().browse(session_id)
        if not session.exists():
            return request.redirect('/history')
        allowed = self._is_admin() or (session.mahasiswa_id.user_id.id == request.env.user.id) or (session.alumni_id.user_id.id == request.env.user.id)
        if not allowed:
            return request.redirect('/history')
        values = self._layout_values('history')
        values.update({'session': session, 'history_role': role})
        return request.render('mentorize.page_history_detail', values)

    # ---------- reports ----------
    @http.route(['/reports', '/laporan'], type='http', auth='user', website=True, sitemap=False)
    def reports(self, **kwargs):
        reports = request.env['mentorize.pelanggaran'].sudo().search([('pelapor_id', '=', request.env.user.id)], order='create_date desc')
        values = self._layout_values('reports')
        values.update({'reports': reports, 'success': kwargs.get('success'), 'error': kwargs.get('error')})
        return request.render('mentorize.page_reports', values)

    @http.route('/report/create', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def report_create(self, **kwargs):
        dilaporkan_id = int(kwargs.get('dilaporkan_id') or 0)
        session_id = int(kwargs.get('session_id') or 0)
        request_id = int(kwargs.get('request_id') or 0)
        title = kwargs.get('judul') or kwargs.get('alasan') or 'Laporan pengguna'
        report = request.env['mentorize.pelanggaran'].sudo().create({
            'pelapor_id': request.env.user.id,
            'dilaporkan_id': dilaporkan_id or False,
            'session_id': session_id or False,
            'request_id': request_id or False,
            'kategori': kwargs.get('kategori') or 'lainnya',
            'judul': title,
            'deskripsi': kwargs.get('deskripsi') or '',
            'status': 'baru',
        })
        admins = request.env['res.users'].sudo().search([('mentorize_role', '=', 'admin')])
        for admin in admins:
            request.env['mentorize.notification'].sudo().create_notification(admin, 'Laporan baru', '%s membuat laporan: %s' % (request.env.user.name, title), 'report_new', '/admin/reports')
        self._log_activity('report', 'Membuat laporan: %s' % title, 'mentorize.pelanggaran', report.id)
        return request.redirect('/reports?success=1')

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