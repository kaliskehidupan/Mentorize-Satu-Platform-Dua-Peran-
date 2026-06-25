# -*- coding: utf-8 -*-
# Base controller berisi helper umum, mirip service/middleware kecil pada Laravel.
# Helper di sini dipakai ulang oleh controller auth, dashboard, profile, mentor, chat, admin, dan lainnya.

import base64
import json
import mimetypes
import re
from datetime import datetime, timedelta, time

import pytz
from html import escape

from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import AccessDenied


class MentorizeBaseController(http.Controller):
    # Helper umum dipindahkan dari main.py agar route tidak menumpuk dalam satu file.
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
        user = request.env.user
        role = self._infer_user_role(user) if not user._is_public() else False

        # Hitung apakah profil user sudah lengkap untuk ditampilkan banner peringatan
        profile_incomplete = False
        if not user._is_public() and role in ('mahasiswa', 'alumni'):
            try:
                if role == 'mahasiswa':
                    mahasiswa = self._current_mahasiswa()
                    if mahasiswa and not mahasiswa.profile_complete:
                        profile_incomplete = True
                elif role == 'alumni':
                    alumni = self._current_alumni()
                    if alumni and not alumni.profile_complete:
                        profile_incomplete = True
            except Exception:
                pass

        return {
            'user': user,
            'role': role,
            'active_menu': active,
            'notifications': self._get_notifications(),
            'unread_count': self._unread_count(),
            'profile_incomplete': profile_incomplete,
            'is_admin_page': False,
            # Helper tampilan waktu. Jangan pakai strftime langsung di template,
            # karena datetime Odoo tersimpan UTC dan perlu ditampilkan sebagai WIB.
            'fmt_dt': lambda dt, fmt='%d %b %Y %H:%M': self._format_user_datetime(dt, fmt),
            'fmt_date': lambda dt, fmt='%d %b %Y': self._format_user_datetime(dt, fmt),
            'fmt_time': lambda dt, fmt='%H:%M': self._format_user_datetime(dt, fmt),
            'scheduling_timezone': 'Asia/Jakarta',
        }


    def _unique_records_by_name(self, records, selected_ids=None):
        """Menghapus pilihan minat/skill yang tampil dobel berdasarkan nama.

        Data lama di database kadang sudah punya nama yang sama lebih dari sekali.
        Helper ini hanya merapikan tampilan/form tanpa menghapus data database,
        sehingga aman untuk project yang sudah berjalan. Jika user sebelumnya memilih
        salah satu record duplikat, record terpilih itu diprioritaskan tetap muncul.
        """
        selected_ids = set(selected_ids or [])
        chosen = {}
        for rec in records:
            name = (rec.name or '').strip()
            key = name.casefold() if name else ('id-%s' % rec.id)
            current = chosen.get(key)
            if not current:
                chosen[key] = rec
            elif rec.id in selected_ids and current.id not in selected_ids:
                chosen[key] = rec
        ordered = sorted(chosen.values(), key=lambda r: ((r.name or '').casefold(), r.id))
        return records.browse([rec.id for rec in ordered])

    def _verify_mahasiswa_identity(self, nim, name):
        """Hook untuk integrasi API NIM asli nanti. Saat ini sengaja dibuat lolos dulu."""
        return True, 'OK'

    def _verify_alumni_identity(self, kapa, name):
        """Hook untuk integrasi API KAPA asli nanti. Saat ini sengaja dibuat lolos dulu."""
        return True, 'OK'

    def _collect_alumni_experience_vals(self, kwargs):
        """Ambil experience alumni dari form profil.
        Form mengirim array: exp_perusahaan[], exp_posisi[], exp_tahun_mulai[], exp_tahun_selesai[], exp_deskripsi[].
        """
        form = request.httprequest.form
        perusahaan_list = form.getlist('exp_perusahaan')
        posisi_list = form.getlist('exp_posisi')
        tahun_mulai_list = form.getlist('exp_tahun_mulai')
        tahun_selesai_list = form.getlist('exp_tahun_selesai')
        deskripsi_list = form.getlist('exp_deskripsi')

        max_len = max(
            len(perusahaan_list),
            len(posisi_list),
            len(tahun_mulai_list),
            len(tahun_selesai_list),
            len(deskripsi_list),
            0,
        )

        experiences = []
        for idx in range(max_len):
            perusahaan = (perusahaan_list[idx] if idx < len(perusahaan_list) else '').strip()
            posisi = (posisi_list[idx] if idx < len(posisi_list) else '').strip()
            tahun_mulai = (tahun_mulai_list[idx] if idx < len(tahun_mulai_list) else '').strip()
            tahun_selesai = (tahun_selesai_list[idx] if idx < len(tahun_selesai_list) else '').strip()
            deskripsi = (deskripsi_list[idx] if idx < len(deskripsi_list) else '').strip()

            # Abaikan baris yang benar-benar kosong.
            if not (perusahaan or posisi or tahun_mulai or tahun_selesai or deskripsi):
                continue

            experiences.append({
                'nama_experience': posisi or perusahaan or 'Pengalaman Kerja',
                'perusahaan': perusahaan,
                'posisi': posisi,
                'tahun_mulai': tahun_mulai,
                'tahun_selesai': tahun_selesai,
                'deskripsi': deskripsi,
            })

        return experiences

    def _count_complete_experiences(self, experiences):
        total = 0
        for exp in experiences:
            if exp.get('perusahaan') and exp.get('posisi') and (exp.get('tahun_mulai') or exp.get('tahun_selesai')):
                total += 1
        return total

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
        """Menentukan apakah chat boleh dipakai.

        Helper ini juga menjalankan sinkronisasi lifecycle sesi agar chat langsung
        terbuka ketika jadwal sudah tiba, meskipun cron belum sempat berjalan.
        """
        if not room or not room.exists():
            return False

        session = room.session_id
        if session:
            self._sync_session_lifecycle(session)
            room.invalidate_recordset()
            session.invalidate_recordset()

        if room.status != 'active':
            return False
        if room.request_id and room.request_id.status != 'approved':
            return False
        if not session:
            return True
        if session.status not in ['active', 'extended']:
            return False
        if session.expired_at and fields.Datetime.now() > session.expired_at:
            self._sync_session_lifecycle(session)
            return False
        return True

    # ==============================
    # Helper waktu, lifecycle sesi, dan kalender
    # ==============================
    def _user_timezone(self):
        """Timezone resmi untuk jadwal Mentorize.

        Mentorize dipakai di lingkungan UNISA/Yogyakarta, sehingga kalender custom
        di browser diperlakukan sebagai waktu lokal WIB. Nilai datetime tetap
        disimpan ke database Odoo sebagai UTC-naive, tetapi semua input dan
        tampilan jadwal dikonversi dari/ke Asia/Jakarta agar tidak bergeser 7 jam.
        Jika suatu saat perlu diubah, cukup isi System Parameters:
        ``mentorize.scheduling_timezone``.
        """
        tz_name = request.env['ir.config_parameter'].sudo().get_param(
            'mentorize.scheduling_timezone',
            'Asia/Jakarta',
        ) or 'Asia/Jakarta'
        try:
            return pytz.timezone(tz_name)
        except Exception:
            return pytz.timezone('Asia/Jakarta')

    def _parse_user_datetime(self, value):
        """Mengubah input tanggal dari browser menjadi datetime UTC-naive untuk Odoo.

        Browser mengirim nilai datetime-local sebagai waktu lokal user. Odoo menyimpan
        datetime sebagai UTC tanpa timezone, jadi nilai harus dikonversi agar sesi tidak
        salah dianggap belum mulai atau sudah habis.
        """
        value = (value or '').strip()
        if not value:
            return False

        parsed = False
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except Exception:
                pass
        if not parsed:
            return False

        user_tz = self._user_timezone()
        local_dt = user_tz.localize(parsed) if parsed.tzinfo is None else parsed.astimezone(user_tz)
        utc_dt = local_dt.astimezone(pytz.UTC).replace(tzinfo=None)
        return utc_dt

    def _format_user_datetime(self, dt, fmt='%d %b %Y %H:%M'):
        """Format datetime Odoo UTC-naive ke timezone jadwal Mentorize (WIB)."""
        if not dt:
            return '-'
        try:
            value = fields.Datetime.to_datetime(dt)
            if value.tzinfo is None:
                value = pytz.UTC.localize(value)
            return value.astimezone(self._user_timezone()).strftime(fmt)
        except Exception:
            return str(dt)

    def _schedule_is_past_or_now(self, dt):
        """True jika jadwal UTC-naive sudah lewat atau sama dengan waktu sekarang."""
        if not dt:
            return True
        try:
            return fields.Datetime.to_datetime(dt) <= fields.Datetime.now()
        except Exception:
            return True

    def _sync_session_lifecycle(self, sessions=False):
        """Fallback aktivasi sesi agar tidak hanya bergantung pada cron.

        Setiap dashboard/chat dibuka, helper ini memastikan:
        - sesi terjadwal yang waktunya sudah tiba berubah menjadi aktif;
        - sesi aktif yang melewati batas 2 x 24 jam berubah menjadi waktu habis.
        Dengan ini chat tidak terkunci hanya karena cron belum jalan.
        """
        Session = request.env['mentorize.session'].sudo()
        now = fields.Datetime.now()

        if not sessions:
            user = request.env.user
            domain = ['|', ('mahasiswa_id.user_id', '=', user.id), ('alumni_id.user_id', '=', user.id)]
            sessions = Session.search(domain)
        else:
            sessions = sessions.sudo()

        to_activate = sessions.filtered(lambda s: s.status in ['scheduled', 'extended'] and s.tanggal_mentoring and s.tanggal_mentoring <= now)
        if to_activate:
            to_activate._activate_session()

        to_expire = sessions.filtered(lambda s: s.status == 'active' and s.expired_at and s.expired_at <= now)
        Notification = request.env['mentorize.notification'].sudo()
        for rec in to_expire:
            rec.write({'status': 'time_expired'})
            for target in [rec.mahasiswa_id.user_id, rec.alumni_id.user_id]:
                if target:
                    Notification.create_notification(
                        target,
                        'Waktu mentoring habis',
                        'Waktu sesi "%s" sudah habis. Ajukan tambah waktu atau ajukan penyelesaian sesi.' % (rec.topik or 'Mentoring'),
                        notif_type='session_expired',
                        url='/chat?room_id=%s' % (rec.request_id.room_chat_id.id if rec.request_id.room_chat_id else ''),
                    )
        return True

    def _chat_lock_reason(self, room):
        """Memberi alasan jelas kenapa form pesan terkunci."""
        if not room or not room.exists():
            return 'Ruang pesan belum tersedia.'
        if room.status != 'active':
            return 'Ruang pesan belum aktif atau sudah ditutup.'
        if room.request_id and room.request_id.status != 'approved':
            return 'Pengajuan mentoring belum diterima alumni.'
        session = room.session_id
        if not session:
            return ''
        if session.status == 'scheduled':
            return 'Sesi belum dimulai. Sesi akan aktif pada %s.' % self._format_user_datetime(session.tanggal_mentoring)
        if session.status == 'time_expired':
            return 'Waktu sesi 2 x 24 jam sudah habis. Ajukan tambah waktu atau ajukan penyelesaian sesi.'
        if session.status == 'extension_pending':
            return 'Pengajuan tambah waktu sedang menunggu persetujuan mentor.'
        if session.status == 'end_requested':
            return 'Pengajuan penyelesaian sesi sedang menunggu persetujuan mentor.'
        if session.status in ['completed', 'stopped', 'cancelled']:
            return 'Sesi sudah selesai/dihentikan. Pesan lama tetap bisa dibaca.'
        if session.expired_at and fields.Datetime.now() > session.expired_at:
            return 'Waktu sesi 2 x 24 jam sudah habis. Ajukan tambah waktu atau ajukan penyelesaian sesi.'
        return ''

    def _profile_image_url(self, user, size='image_128'):
        """URL foto profil dengan cache buster agar foto terbaru langsung tampil."""
        if not user:
            return '/web/static/img/placeholder.png'
        unique = ''
        try:
            unique = fields.Datetime.to_string(user.write_date or user.create_date or fields.Datetime.now()).replace(' ', '').replace(':', '').replace('-', '')
        except Exception:
            unique = str(user.id)
        return '/web/image/res.users/%s/%s?unique=%s' % (user.id, size, unique)

    def _busy_dates_for_alumni(self, alumni, exclude_session=False):
        """Menghasilkan daftar tanggal yang tidak boleh dipilih pada kalender custom.

        Tanggal dikunci berdasarkan rentang 2 x 24 jam setiap sesi milik mentor yang
        statusnya sudah menyita kalender.
        """
        if not alumni:
            return [], []
        busy_statuses = [
            'scheduled', 'active', 'time_expired', 'extension_pending', 'extended',
            'end_requested', 'reschedule_requested', 'stop_requested'
        ]
        sessions = request.env['mentorize.session'].sudo().search([
            ('alumni_id', '=', alumni.id),
            ('status', 'in', busy_statuses),
        ])
        user_tz = self._user_timezone()
        busy_dates = set()
        ranges = []
        for sesi in sessions:
            if exclude_session and sesi.id == exclude_session.id:
                continue
            start_dt = sesi.tanggal_mentoring
            if not start_dt:
                continue
            end_dt = sesi.session_end_at or sesi.expired_at or (start_dt + timedelta(hours=sesi.duration_hours or 48))
            try:
                local_start = pytz.UTC.localize(start_dt).astimezone(user_tz) if start_dt.tzinfo is None else start_dt.astimezone(user_tz)
                local_end = pytz.UTC.localize(end_dt).astimezone(user_tz) if end_dt.tzinfo is None else end_dt.astimezone(user_tz)
            except Exception:
                local_start, local_end = start_dt, end_dt
            current_date = local_start.date()
            while current_date <= local_end.date():
                busy_dates.add(current_date.isoformat())
                current_date += timedelta(days=1)
            ranges.append({
                'session_id': sesi.id,
                'start': self._format_user_datetime(start_dt),
                'end': self._format_user_datetime(end_dt),
                'status': sesi.status,
            })
        return sorted(busy_dates), ranges

    # ==============================
    # Helper upload file/foto
    # ==============================
    # Semua upload di Mentorize dibatasi maksimal 2 MB agar database dan filestore tetap ringan.
    MAX_UPLOAD_SIZE = 2 * 1024 * 1024
    IMAGE_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp'}
    CHAT_FILE_MIMETYPES = IMAGE_MIMETYPES.union({
        'application/pdf',
        'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    })

    def _read_upload(self, upload, allowed_mimetypes=None, label='File'):
        """Membaca file upload dari form HTTP dan melakukan validasi ukuran/tipe.

        Return: (ok, message, info)
        - ok True berarti file valid.
        - info berisi filename, mimetype, size, dan data bytes.
        """
        if not upload or not getattr(upload, 'filename', None):
            return True, '', False

        filename = (upload.filename or '').strip()
        data = upload.read()
        size = len(data or b'')
        guessed_type = mimetypes.guess_type(filename)[0]
        mimetype = upload.mimetype or guessed_type or 'application/octet-stream'

        if size <= 0:
            return False, '%s tidak boleh kosong.' % label, False
        if size > self.MAX_UPLOAD_SIZE:
            return False, '%s maksimal 2 MB.' % label, False

        if allowed_mimetypes and mimetype not in allowed_mimetypes:
            return False, '%s memiliki tipe file yang tidak diizinkan.' % label, False

        return True, '', {
            'filename': filename,
            'mimetype': mimetype,
            'size': size,
            'data': data,
        }

    def _create_private_attachment(self, info, res_model, res_id):
        """Menyimpan file ke ir.attachment secara private.

        Attachment tidak dibuat public sehingga akses tampil/download tetap lewat route yang memeriksa hak akses.
        """
        if not info:
            return request.env['ir.attachment'].sudo().browse([])
        return request.env['ir.attachment'].sudo().create({
            'name': info['filename'],
            'datas': base64.b64encode(info['data']),
            'res_model': res_model,
            'res_id': res_id,
            'mimetype': info['mimetype'],
            'public': False,
        })

    def _validate_profile_photo(self, upload):
        """Validasi foto profil. Foto profil hanya boleh JPG, PNG, atau WEBP dan maksimal 2 MB."""
        return self._read_upload(upload, self.IMAGE_MIMETYPES, 'Foto profil')

    # ==============================
    # Helper kalender sesi mentoring
    # ==============================
    def _session_window(self, start_dt):
        """Menghasilkan rentang sesi mentoring 2 x 24 jam dari tanggal mulai."""
        if not start_dt:
            return False, False
        return start_dt, start_dt + timedelta(hours=48)

    def _mentor_schedule_conflict(self, alumni, start_dt, exclude_session=False):
        """Cek apakah mentor sudah punya sesi pada rentang 2 x 24 jam yang bertabrakan.

        Tanggal dianggap terpakai jika sesi mentor sudah disetujui/terjadwal/aktif/menunggu perpanjangan.
        Pending request belum mengunci kalender karena belum diterima alumni.
        """
        if not alumni or not start_dt:
            return False
        start_dt, end_dt = self._session_window(start_dt)
        busy_statuses = [
            'scheduled', 'active', 'time_expired', 'extension_pending', 'extended',
            'end_requested', 'reschedule_requested', 'stop_requested'
        ]
        sessions = request.env['mentorize.session'].sudo().search([
            ('alumni_id', '=', alumni.id),
            ('status', 'in', busy_statuses),
        ])
        for sesi in sessions:
            if exclude_session and sesi.id == exclude_session.id:
                continue
            sesi_start = sesi.tanggal_mentoring
            if not sesi_start:
                continue
            sesi_end = sesi.session_end_at or sesi.expired_at or (sesi_start + timedelta(hours=48))
            if sesi_start < end_dt and sesi_end > start_dt:
                return sesi
        return False

    def _other_user_for_room(self, room):
        if not room:
            return request.env['res.users'].sudo().browse([])
        return room.alumni_user_id if room.mahasiswa_user_id.id == request.env.user.id else room.mahasiswa_user_id


    def _is_valid_email(self, email):
        """Validasi sederhana untuk email notifikasi Mentorize."""
        email = (email or '').strip()
        if not email:
            return False
        return bool(re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email))

    def _is_user_identity_completed(self, user=None):
        """Cek apakah identitas dasar sudah bukan fallback SSO.

        SSO kampus kadang hanya mengirim NIM, sehingga user awal bisa menjadi
        name=NIM dan email=NIM. Kondisi seperti ini belum dianggap lengkap.
        """
        user = (user or request.env.user).sudo()
        login = (user.login or '').strip()
        name = (user.name or '').strip()
        email = (user.email or '').strip()
        return bool(name and name != login and self._is_valid_email(email) and email != login)

    def _is_profile_complete_for_user(self, user=None, role=None):
        user = user or request.env.user
        role = role or self._infer_user_role(user)

        if role == 'admin':
            return True

        if not self._is_user_identity_completed(user):
            return False

        if role == 'alumni':
            alumni = request.env['mentorize.alumni'].sudo().search([('user_id', '=', user.id)], limit=1)
            return bool(alumni and alumni.profile_complete)

        mahasiswa = request.env['mentorize.mahasiswa'].sudo().search([('user_id', '=', user.id)], limit=1)
        return bool(mahasiswa and mahasiswa.profile_complete)

    def _profile_setup_url_for_user(self, user=None, role=None):
        user = user or request.env.user
        role = role or self._infer_user_role(user)
        return '/alumni/profile/setup' if role == 'alumni' else '/profile/setup'

    def _ensure_profile_complete_or_redirect(self, allow_settings=False, json_response=False):
        """Middleware kecil untuk mengunci fitur sampai profil lengkap.

        Halaman setup profil, settings, logout, dan admin tidak dikunci agar user
        tetap bisa memperbaiki data atau keluar dari akun.
        """
        if request.env.user._is_public():
            return False

        role = self._infer_user_role(request.env.user)
        if role == 'admin':
            return False

        path = request.httprequest.path or ''
        allowed_prefixes = (
            '/profile', '/alumni/profile/setup', '/settings', '/logout/confirm',
            '/sso/logout', '/web/image', '/mentorize/static'
        )
        if allow_settings or path.startswith(allowed_prefixes):
            return False

        if self._is_profile_complete_for_user(request.env.user, role):
            return False

        message = 'Lengkapi profil terlebih dahulu sebelum menggunakan Mentorize.'
        if json_response:
            return self._json({'success': False, 'error': message, 'redirect': self._profile_setup_url_for_user(request.env.user, role)}, status=403)
        return request.redirect(self._profile_setup_url_for_user(request.env.user, role) + '?error=' + message)

    def _mentorize_notification_email(self, user):
        """Ambil email tujuan notifikasi jika user mengaktifkan notifikasi email."""
        if not user or not user.exists():
            return False
        if not getattr(user, 'mentorize_notification_email', False):
            return False
        email = (user.sudo().email or '').strip()
        return email if self._is_valid_email(email) else False

    def _plain_to_html(self, text):
        """Konversi teks biasa menjadi HTML sederhana untuk body email."""
        lines = escape(text or '').splitlines() or ['']
        return '<br/>'.join(lines)

    def _send_mentorize_email(self, user, subject, body_text='', body_html=False, force=False):
        """Kirim email via mail.mail Odoo.

        Email hanya dikirim jika user punya email valid dan notifikasi email aktif.
        Parameter force=True dipakai untuk kasus administratif jika tetap ingin
        mengirim meski toggle notifikasi user nonaktif.
        """
        if not user or not user.exists():
            return False
        email = (user.sudo().email or '').strip()
        if not self._is_valid_email(email):
            return False
        if not force and not getattr(user, 'mentorize_notification_email', False):
            return False

        company = request.env.company.sudo() if request.env.company else False
        config = request.env['ir.config_parameter'].sudo()
        email_from = (
            config.get_param('mail.default.from')
            or (company.email if company else False)
            or 'Mentorize <no-reply@mentorize.local>'
        )
        html_body = body_html or self._plain_to_html(body_text)
        try:
            mail = request.env['mail.mail'].sudo().create({
                'subject': subject or 'Notifikasi Mentorize',
                'body_html': html_body,
                'email_to': email,
                'email_from': email_from,
                'auto_delete': False,
            })
            mail.send()
            return True
        except Exception as exc:
            # Jangan sampai email gagal membuat fitur utama gagal.
            try:
                import logging
                logging.getLogger(__name__).exception('Gagal mengirim email Mentorize ke %s: %s', email, exc)
            except Exception:
                pass
            return False

    def _email_subject(self, title):
        return '[Mentorize] %s' % (title or 'Notifikasi')

    def _admin_base_values(self, active='dashboard'):
        values = self._layout_values(active)
        values.update({'is_admin_page': True})
        return values


