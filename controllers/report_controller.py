# -*- coding: utf-8 -*-
# Controller laporan. Mahasiswa/alumni bisa melapor ke admin dengan deskripsi wajib dan bukti gambar maksimal 2 MB.

import base64

from odoo import http
from odoo.http import request

from .base import MentorizeBaseController


class MentorizeReportController(MentorizeBaseController):
    # ---------- Daftar Laporan User ----------
    @http.route(['/reports', '/laporan'], type='http', auth='user', website=True, sitemap=False)
    def reports(self, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        reports = request.env['mentorize.pelanggaran'].sudo().search(
            [('pelapor_id', '=', request.env.user.id)],
            order='create_date desc'
        )
        values = self._layout_values('reports')
        values.update({
            'reports': reports,
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
        })
        return request.render('mentorize.page_reports', values)

    # ---------- Buat Laporan ----------
    @http.route('/report/create', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def report_create(self, **kwargs):
        redirect = self._ensure_profile_complete_or_redirect()
        if redirect:
            return redirect
        """Membuat laporan ke admin. Deskripsi wajib dan bukti gambar opsional maksimal 2 MB."""
        dilaporkan_id = int(kwargs.get('dilaporkan_id') or 0)
        session_id = int(kwargs.get('session_id') or 0)
        request_id = int(kwargs.get('request_id') or 0)
        title = (kwargs.get('judul') or kwargs.get('alasan') or 'Laporan pengguna').strip()
        deskripsi = (kwargs.get('deskripsi') or '').strip()

        if not deskripsi:
            return request.redirect('/chat?error=Deskripsi laporan wajib diisi')

        image_info = False
        upload = request.httprequest.files.get('bukti_gambar')
        if upload and upload.filename:
            ok, error, image_info = self._read_upload(upload, self.IMAGE_MIMETYPES, 'Gambar bukti')
            if not ok:
                return request.redirect('/chat?error=%s' % error)

        report = request.env['mentorize.pelanggaran'].sudo().create({
            'pelapor_id': request.env.user.id,
            'dilaporkan_id': dilaporkan_id or False,
            'session_id': session_id or False,
            'request_id': request_id or False,
            'kategori': kwargs.get('kategori') or 'lainnya',
            'judul': title,
            'deskripsi': deskripsi,
            'status': 'baru',
        })

        if image_info:
            attachment = self._create_private_attachment(image_info, 'mentorize.pelanggaran', report.id)
            report.write({
                'attachment_id': attachment.id,
                'attachment_name': image_info['filename'],
                'attachment_mimetype': image_info['mimetype'],
                'attachment_size': image_info['size'],
            })

        admins = request.env['res.users'].sudo().search([('mentorize_role', '=', 'admin')])
        for admin in admins:
            request.env['mentorize.notification'].sudo().create_notification(
                admin,
                'Laporan baru',
                '%s membuat laporan: %s' % (request.env.user.name, title),
                'report_new',
                '/admin/reports'
            )
        self._log_activity('report', 'Membuat laporan: %s' % title, 'mentorize.pelanggaran', report.id)
        return request.redirect('/reports?success=1')

    # ---------- Akses Bukti Laporan ----------
    @http.route('/report/attachment/<int:report_id>', type='http', auth='user', website=False, methods=['GET'], csrf=False)
    def report_attachment(self, report_id, **kwargs):
        """Menampilkan bukti gambar laporan hanya untuk pelapor dan admin."""
        report = request.env['mentorize.pelanggaran'].sudo().browse(report_id)
        if not report.exists() or not report.attachment_id:
            return request.not_found()
        allowed = self._is_admin() or report.pelapor_id.id == request.env.user.id
        if not allowed:
            return request.not_found()

        attachment = report.attachment_id.sudo()
        data = base64.b64decode(attachment.datas or b'')
        headers = [
            ('Content-Type', report.attachment_mimetype or attachment.mimetype or 'image/jpeg'),
            ('Content-Length', str(len(data))),
            ('Content-Disposition', 'inline; filename="%s"' % (report.attachment_name or attachment.name or 'bukti-laporan')),
        ]
        return request.make_response(data, headers=headers)
