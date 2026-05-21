from odoo import http
from odoo.http import request


class MentorizeAdminController(http.Controller):

    # ================= LOGIN ADMIN =================
    @http.route('/mentorize/admin/login', type='http', auth='public', website=True)
    def admin_login(self, **kwargs):

        error = kwargs.get('error')

        return request.render('mentorize.admin_login', {
            'error': error
        })

    @http.route(
        '/mentorize/admin/login/submit',
        type='http',
        auth='public',
        website=True,
        methods=['POST'],
        csrf=False
    )
    def admin_login_submit(self, **kwargs):

        email = kwargs.get('email')
        password = kwargs.get('password')

        try:
            uid = request.session.authenticate(
                request.db,
                email,
                password
            )

            if uid:
                user = request.env['res.users'].browse(uid)

                if user.mentorize_role == 'admin':
                    return request.redirect('/mentorize/admin/dashboard')

        except:
            pass

        return request.redirect('/mentorize/admin/login?error=1')

    # ================= DASHBOARD =================
    # =========================================================
    # ADMIN DASHBOARD
    # =========================================================

    @http.route(
        '/mentorize/admin/dashboard',
        auth='user',
        website=True
    )
    def mentorize_admin_dashboard(self, **kwargs):

        users = request.env['res.users'].sudo()


        # =====================================================
        # TOTAL MAHASISWA
        # =====================================================

        total_mahasiswa = users.search_count([
            ('mentorize_role', '=', 'mahasiswa')
        ])


        # =====================================================
        # TOTAL ALUMNI
        # =====================================================

        total_alumni = users.search_count([
            ('mentorize_role', '=', 'alumni')
        ])


        # =====================================================
        # USER SUSPENDED
        # =====================================================

        suspended_users = users.search_count([
            ('active', '=', False)
        ])


        # =====================================================
        # MENTORING AKTIF
        # sementara dummy dulu
        # nanti diganti model mentoring asli
        # =====================================================

        mentoring_active = 0


        # =====================================================
        # RECENT USERS
        # =====================================================

        recent_users = users.search(
            [],
            limit=5,
            order='create_date desc'
        )


        values = {

            'total_mahasiswa': total_mahasiswa,
            'total_alumni': total_alumni,
            'suspended_users': suspended_users,
            'mentoring_active': mentoring_active,
            'recent_users': recent_users,

            'user_chart_data': [
                total_mahasiswa,
                total_alumni,
                mentoring_active,
                suspended_users
            ],


        }


        return request.render(
            'mentorize.dashboard_admin',
            values
        )


    # ================= PROFIL ADMIN =================
    @http.route('/mentorize/admin/profile', auth='user', website=True)
    def admin_profile(self, **kw):

        values = {
            'user': request.env.user
        }

        return request.render(
            'mentorize.profil_admin',
            values
        )
    
    @http.route('/mentorize/admin/profil/update',
             type='http',
             auth='user',
             methods=['POST'],
             website=True,
             csrf=True)
    def update_admin_profile(self, **post):

        user = request.env.user

        # update nama
        user.sudo().write({
            'name': post.get('name')
        })

        # update email/login
        if post.get('email'):
            user.sudo().write({
                'email': post.get('email'),
                'login': post.get('email')
            })

        # update password
        password = post.get('password')
        confirm = post.get('confirm_password')

        if password and password == confirm:
            user.sudo().write({
                'password': password
            })

        return request.redirect('/mentorize/admin/profile')
    
    # ADMIN MAHASISWA
    @http.route('/mentorize/admin/users',
                type='http',
                auth='user',
                website=True)
    def mentorize_admin_users(self, search='', role='', **kwargs):

        domain = [
            ('mentorize_role', '!=', False)
        ]

        if search:

            domain += ['|',
                ('name', 'ilike', search),
                ('login', 'ilike', search)
            ]

        if role:

            domain += [
                ('mentorize_role', '=', role)
            ]

        users = request.env['res.users'].sudo().search(domain)

        user_data = []

        for user in users:

            filled = 0
            total = 6

            fields_check = [
                user.name,
                user.login,
                user.bio,
                user.jurusan,
                user.tujuan_karir,
                user.availability
            ]

            for field in fields_check:
                if field:
                    filled += 1

            percentage = int((filled / total) * 100)

            user_data.append({
                'id': user.id,
                'name': user.name,
                'email': user.login,
                'role': user.mentorize_role,
                'active': user.active,
                'verified': user.is_verified,
                'progress': percentage,
                'jurusan': user.jurusan or '-',
            })

        total_users = len(user_data)

        total_active = len([
            u for u in user_data if u['active']
        ])

        total_suspend = len([
            u for u in user_data if not u['active']
        ])

        return request.render(
            'mentorize.admin_users',
            {
                'users': user_data,
                'total_users': total_users,
                'total_active': total_active,
                'total_suspend': total_suspend,
                'search': search,
                'selected_role': role,
            }
        )

    @http.route('/mentorize/admin/user/suspend/<int:user_id>',
                type='http',
                auth='user',
                website=True)
    def suspend_user(self, user_id):

        user = request.env['res.users'].sudo().browse(user_id)
        user.active = False

        return request.redirect('/mentorize/admin/users')

    @http.route('/mentorize/admin/user/activate/<int:user_id>',
                type='http',
                auth='user',
                website=True)
    def activate_user(self, user_id):

        user = request.env['res.users'].sudo().browse(user_id)
        user.active = True

        return request.redirect('/mentorize/admin/users')
    

    # ================= LAPORAN =================
    @http.route('/mentorize/admin/laporan', auth='user', website=True)
    def admin_laporan(self, **kw):

        # ambil data laporan dari model (nanti disambungkan ke DB)
        laporan_records = request.env['mentorize.laporan'].sudo().search([])

        laporan = []
        for item in laporan_records:
            laporan.append({
                "id": item.id,
                "mahasiswa": item.mahasiswa_id.name,
                "judul": item.judul,
                "tanggal": item.create_date.strftime("%Y-%m-%d") if item.create_date else "-",
                "status": item.status,
            })

        return request.render("mentorize.admin_laporan", {
            "laporan": laporan,

            # STATISTIK (untuk XML kamu)
            "total_laporan": len(laporan),
            "total_pending": len([x for x in laporan if x["status"] == "pending"]),
            "total_approved": len([x for x in laporan if x["status"] == "approved"]),
            "total_rejected": len([x for x in laporan if x["status"] == "rejected"]),
        })
    
    @http.route('/mentorize/admin/laporan/approve/<int:laporan_id>', auth='user', website=True)
    def approve_laporan(self, laporan_id):

        laporan = request.env['mentorize.laporan'].sudo().browse(laporan_id)

        if laporan.exists():
            laporan.write({'status': 'approved'})

        return request.redirect('/mentorize/admin/laporan')
    
    @http.route('/mentorize/admin/laporan/reject/<int:laporan_id>', auth='user', website=True)
    def reject_laporan(self, laporan_id):

        laporan = request.env['mentorize.laporan'].sudo().browse(laporan_id)

        if laporan.exists():
            laporan.write({'status': 'rejected'})

        return request.redirect('/mentorize/admin/laporan')
    

    #PELANGGARAN-----
    @http.route('/mentorize/admin/pelanggaran', auth='user', website=True)
    def admin_pelanggaran(self, **kw):

        reports = request.env['mentorize.pelanggaran'].sudo().search([])

        data = []
        for r in reports:
            data.append({
                "id": r.id,
                "pelapor": r.pelapor_id.name,
                "dilaporkan": r.dilaporkan_id.name,
                "alasan": r.alasan,
                "status": r.status,
            })

        return request.render("mentorize.admin_pelanggaran", {
            "pelanggaran": data,
            "total": len(data),
            "pending": len([x for x in data if x["status"] == "pending"]),
        })
    
    @http.route('/mentorize/admin/pelanggaran/disable/<int:report_id>', auth='user', website=True)
    def disable_user(self, report_id):

        report = request.env['mentorize.pelanggaran'].sudo().browse(report_id)

        if report.exists():
            # disable user yang dilaporkan
            report.dilaporkan_id.write({'active': False})

            report.write({
                'status': 'closed',
                'action': 'disabled'
            })

        return request.redirect('/mentorize/admin/pelanggaran')
    
    @http.route('/mentorize/admin/pelanggaran/ignore/<int:report_id>', auth='user', website=True)
    def ignore_report(self, report_id):

        report = request.env['mentorize.pelanggaran'].sudo().browse(report_id)

        if report.exists():
            report.write({
                'status': 'closed',
                'action': 'ignored'
            })

        return request.redirect('/mentorize/admin/pelanggaran')
    

        #ADMIN AKTIVITAS
    @http.route('/mentorize/admin/aktivitas', auth='user', website=True)
    def admin_aktivitas(self, **kw):

        logs = request.env['mentorize.activity'].sudo().search([], order="timestamp desc")

        data = []
        for l in logs:
            data.append({
                "user": l.user_id.name,
                "type": l.activity_type,
                "desc": l.description,
                "time": l.timestamp.strftime("%Y-%m-%d %H:%M") if l.timestamp else "-",
            })

        return request.render("mentorize.admin_aktivitas", {
            "logs": data,
            "total": len(data),
            "login": len([x for x in data if x["type"] == "login"]),
            "logout": len([x for x in data if x["type"] == "logout"]),
        })
    
    #SKILL DAN MINAT
    @http.route('/mentorize/admin/skill-minat', auth='user', website=True)
    def admin_skill_minat(self, **kw):

        records = request.env['mentorize.skill.minat'].sudo().search([])

        data = []
        for r in records:
            data.append({
                "user": r.user_id.name,
                "skill": r.skill_name,
                "level": r.skill_level,
                "interest": r.interest,
            })

        return request.render("mentorize.admin_skill_minat", {
            "skills": data,
            "total": len(data),
            "beginner": len([x for x in data if x["level"] == "beginner"]),
            "intermediate": len([x for x in data if x["level"] == "intermediate"]),
            "advanced": len([x for x in data if x["level"] == "advanced"]),
        })