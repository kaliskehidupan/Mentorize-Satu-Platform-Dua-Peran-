{
    'name': 'Mentorize',
    'version': '1.0.0',
    'summary': 'Platform Mentorship Alumni-Mahasiswa UNISA Yogyakarta',
    'description': 'Sistem mentoring berbasis web untuk menghubungkan mahasiswa dengan alumni sebagai mentor.',
    'author': 'Tim 3 - Teknologi Informasi UNISA',
    'category': 'Education',
    'depends': ['base', 'website', 'mail'],
    'data': [
    'security/mentorize_groups.xml',
    'security/ir.model.access.csv',

    'views/backend/admin_views.xml',

    'views/templates/layout.xml',
    'views/templates/login.xml',
    'views/templates/forgot_password.xml',
    'views/templates/register.xml',

    'views/templates/dashboard_mahasiswa.xml',
    'views/templates/dashboard_alumni.xml',
    'views/templates/dashboard_admin.xml',

    'views/templates/page_list_mentor.xml',
    'views/templates/page_detail_mentor.xml',
    'views/templates/page_riwayat_mahasiswa.xml',
    'views/templates/page_rekomendasi_mentor.xml',
    'views/templates/page_profil_mahasiswa.xml',
    'views/templates/page_edit_profil_mahasiswa.xml',
],
    'assets': {
        'web.assets_frontend': [
            'mentorize/static/src/css/mentorize.css',
            'mentorize/static/src/js/mentorize.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
