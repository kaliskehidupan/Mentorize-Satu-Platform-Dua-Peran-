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


class MentorizeAdminController(MentorizeBaseController):
    # Semua method di class ini adalah route Odoo untuk fitur yang sesuai nama file.
    # ---------- admin dashboard dan halaman admin ----------
    # Route admin_dashboard: menangani request web untuk fitur ini.
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
        # Verifikasi manual alumni tidak lagi dipakai karena role alumni sudah divalidasi oleh SSO.
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


    # Route admin_users: menangani request web untuk fitur ini.
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
        users = request.env['res.users'].sudo().with_context(active_test=False).search(domain, order='create_date desc')
        values = self._admin_base_values('users')
        values.update({
            'users': users,
            'search': search,
            'selected_role': role,
            'total_users': len(users),
            'total_active': len(users.filtered(lambda u: u.active)),
            'total_suspend': len(users.filtered(lambda u: not u.active)),
        })
        return request.render('mentorize.admin_users', values)


    # Route admin_alumni_verification: menangani request web untuk fitur ini.
    @http.route(['/admin/verification', '/admin/alumni/verification'], type='http', auth='user', website=True, sitemap=False)
    def admin_alumni_verification(self, search='', **kwargs):
        # Verifikasi manual alumni sudah tidak dipakai setelah SSO.
        # Admin mengelola akun dari halaman Kelola Pengguna.
        redirect = self._require_admin()
        if redirect:
            return redirect
        return request.redirect('/admin/users?role=alumni')

    # Route admin_user_detail: menangani request web untuk fitur ini.
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

    # Route admin_verify_user: menangani request web untuk fitur ini.
    @http.route(['/admin/user/<int:user_id>/verify', '/mentorize/admin/user/verify/<int:user_id>'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_verify_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        return request.redirect('/admin/users')

    # Route admin_unverify_user: menangani request web untuk fitur ini.
    @http.route(['/admin/user/<int:user_id>/unverify'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_unverify_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        return request.redirect('/admin/users')

    # Route admin_suspend_user: menangani request web untuk fitur ini.
    @http.route(['/admin/user/<int:user_id>/suspend', '/mentorize/admin/user/suspend/<int:user_id>'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_suspend_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        user_rec = request.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        reason = kwargs.get('reason') or 'Akun dinonaktifkan oleh admin Mentorize.'
        if user_rec.exists() and user_rec.id != request.env.user.id:
            user_rec.write({'active': False, 'mentorize_block_reason': reason})
            request.env['mentorize.notification'].sudo().create_notification(
                user_rec,
                'Akun dinonaktifkan',
                'Akun Mentorize kamu dinonaktifkan oleh admin. Alasan: %s' % reason,
                'report_update',
                '/',
            )
            self._send_mentorize_email(
                user_rec,
                self._email_subject('Akun Mentorize Dinonaktifkan'),
                'Halo %s,\n\nAkun Mentorize kamu dinonaktifkan oleh admin.\nAlasan: %s\n\nJika kamu merasa ini keliru, silakan hubungi admin Mentorize.' % (user_rec.name, reason),
                force=True,
            )
            self._log_activity('admin', 'Admin menonaktifkan akun %s. Alasan: %s' % (user_rec.name, reason), 'res.users', user_rec.id)
        return request.redirect(kwargs.get('next') or '/admin/users')

    # Route admin_activate_user: menangani request web untuk fitur ini.
    @http.route(['/admin/user/<int:user_id>/activate', '/mentorize/admin/user/activate/<int:user_id>'], type='http', auth='user', website=True, methods=['POST', 'GET'], csrf=False)
    def admin_activate_user(self, user_id, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        user_rec = request.env['res.users'].sudo().with_context(active_test=False).browse(user_id)
        if user_rec.exists():
            user_rec.write({'active': True, 'mentorize_block_reason': False})
            request.env['mentorize.notification'].sudo().create_notification(
                user_rec,
                'Akun diaktifkan kembali',
                'Akun Mentorize kamu sudah diaktifkan kembali oleh admin.',
                'info',
                '/',
            )
            self._send_mentorize_email(
                user_rec,
                self._email_subject('Akun Mentorize Diaktifkan Kembali'),
                'Halo %s,\n\nAkun Mentorize kamu sudah diaktifkan kembali oleh admin. Kamu dapat menggunakan layanan Mentorize kembali.' % user_rec.name,
                force=True,
            )
            self._log_activity('admin', 'Admin mengaktifkan kembali akun %s' % user_rec.name, 'res.users', user_rec.id)
        return request.redirect(kwargs.get('next') or '/admin/users')

    # Route admin_skills: menangani halaman analisis minat dan skill pengguna.
    @http.route(['/admin/skills', '/mentorize/admin/skills'], type='http', auth='user', website=True, sitemap=False)
    def admin_skills(self, search='', skill_id='', minat_id='', **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect

        Skill = request.env['mentorize.skill'].sudo()
        Minat = request.env['mentorize.minat'].sudo()
        Mahasiswa = request.env['mentorize.mahasiswa'].sudo()
        Alumni = request.env['mentorize.alumni'].sudo()
        Users = request.env['res.users'].sudo().with_context(active_test=False)

        skills = Skill.search([], order='name asc')
        minats = Minat.search([], order='name asc')

        try:
            selected_skill_id = int(skill_id or 0)
        except Exception:
            selected_skill_id = 0
        try:
            selected_minat_id = int(minat_id or 0)
        except Exception:
            selected_minat_id = 0

        def count_profile(record, field_name):
            return (
                Mahasiswa.search_count([(field_name, 'in', [record.id])])
                + Alumni.search_count([(field_name, 'in', [record.id])])
            )

        skill_stats = [
            {'record': sk, 'name': sk.name, 'count': count_profile(sk, 'skill_ids')}
            for sk in skills
        ]
        skill_stats = sorted([x for x in skill_stats if x['count']], key=lambda x: x['count'], reverse=True)[:10]

        minat_stats = [
            {'record': mn, 'name': mn.name, 'count': count_profile(mn, 'minat_ids')}
            for mn in minats
        ]
        minat_stats = sorted([x for x in minat_stats if x['count']], key=lambda x: x['count'], reverse=True)[:10]

        user_domain = [('mentorize_role', 'in', ['mahasiswa', 'alumni', 'admin'])]
        if search:
            user_domain += ['|', '|', ('name', 'ilike', search), ('login', 'ilike', search), ('email', 'ilike', search)]
        users = Users.search(user_domain, order='mentorize_role asc, name asc')

        rows = []
        for user_rec in users:
            mahasiswa = Mahasiswa.search([('user_id', '=', user_rec.id)], limit=1)
            alumni = Alumni.search([('user_id', '=', user_rec.id)], limit=1)
            profile = mahasiswa or alumni
            skill_ids = profile.skill_ids if profile else Skill.browse([])
            minat_ids = profile.minat_ids if profile else Minat.browse([])

            if selected_skill_id and selected_skill_id not in skill_ids.ids:
                continue
            if selected_minat_id and selected_minat_id not in minat_ids.ids:
                continue

            rows.append({
                'user': user_rec,
                'role': user_rec.mentorize_role or '-',
                'skills': skill_ids,
                'minats': minat_ids,
            })

        values = self._admin_base_values('skills')
        values.update({
            'skills': skills,
            'minats': minats,
            'skill_stats': skill_stats,
            'minat_stats': minat_stats,
            'rows': rows,
            'search': search,
            'selected_skill_id': selected_skill_id,
            'selected_minat_id': selected_minat_id,
            'total_rows': len(rows),
        })
        return request.render('mentorize.admin_skills', values)


    # Route admin_mentoring: menangani request web untuk fitur ini.
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

    # Route admin_feedback: menangani request web untuk fitur ini.
    @http.route(['/admin/feedback', '/mentorize/admin/feedback'], type='http', auth='user', website=True, sitemap=False)
    def admin_feedback(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        feedbacks = request.env['mentorize.feedback'].sudo().search([], order='create_date desc')
        values = self._admin_base_values('feedback')
        values.update({'feedbacks': feedbacks})
        return request.render('mentorize.admin_feedback', values)

    # Route admin_reports: menangani request web untuk fitur ini.
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

    # Route admin_report_update: menangani request web untuk fitur ini.
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
            status_label = dict(report._fields['status'].selection).get(report.status, report.status)
            note = report.admin_note or report.judul or 'Tindakan administratif Mentorize.'

            if action == 'warning' and report.dilaporkan_id:
                request.env['mentorize.notification'].sudo().create_notification(
                    report.dilaporkan_id,
                    'Peringatan akun Mentorize',
                    'Akun kamu mendapat peringatan dari admin. Catatan: %s' % note,
                    'report_update',
                    '/reports',
                )
                self._send_mentorize_email(
                    report.dilaporkan_id,
                    self._email_subject('Peringatan Akun Mentorize'),
                    'Halo %s,\n\nAdmin Mentorize memberikan peringatan terhadap akun kamu berdasarkan hasil moderasi laporan.\nJudul laporan: %s\nCatatan admin: %s\n\nMohon gunakan Mentorize sesuai ketentuan dan etika mentoring.' % (report.dilaporkan_id.name, report.judul or '-', note),
                    force=True,
                )

            if action == 'disabled' and report.dilaporkan_id:
                report.dilaporkan_id.sudo().write({'active': False, 'mentorize_block_reason': note})
                request.env['mentorize.notification'].sudo().create_notification(
                    report.dilaporkan_id,
                    'Akun dinonaktifkan',
                    'Akun Mentorize kamu dinonaktifkan setelah proses moderasi laporan. Catatan: %s' % note,
                    'report_update',
                    '/',
                )
                self._send_mentorize_email(
                    report.dilaporkan_id,
                    self._email_subject('Akun Mentorize Dinonaktifkan'),
                    'Halo %s,\n\nAkun Mentorize kamu dinonaktifkan setelah proses moderasi laporan.\nJudul laporan: %s\nCatatan admin: %s\n\nJika kamu merasa ini keliru, silakan hubungi admin Mentorize.' % (report.dilaporkan_id.name, report.judul or '-', note),
                    force=True,
                )

            request.env['mentorize.notification'].sudo().create_notification(report.pelapor_id, 'Update laporan', 'Laporan "%s" berstatus %s.' % (report.judul, status_label), 'report_update', '/reports')
            self._send_mentorize_email(
                report.pelapor_id,
                self._email_subject('Update Laporan Mentorize'),
                'Halo %s,\n\nLaporan kamu dengan judul "%s" sudah diperbarui oleh admin.\nStatus terbaru: %s\nCatatan admin: %s' % (report.pelapor_id.name, report.judul or '-', status_label, report.admin_note or '-'),
            )
            self._log_activity('admin', 'Admin memproses laporan %s' % report.judul, 'mentorize.pelanggaran', report.id)
        return request.redirect('/admin/reports')

    # Route admin_activities: menangani request web untuk fitur ini.
    @http.route(['/admin/activities', '/mentorize/admin/aktivitas'], type='http', auth='user', website=True, sitemap=False)
    def admin_activities(self, **kwargs):
        redirect = self._require_admin()
        if redirect:
            return redirect
        values = self._admin_base_values('activities')
        values.update({'activities': request.env['mentorize.activity'].sudo().search([], order='timestamp desc', limit=120)})
        return request.render('mentorize.admin_activities', values)


