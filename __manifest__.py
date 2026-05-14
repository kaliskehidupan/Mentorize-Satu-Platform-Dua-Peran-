{
    'name': 'Mentorize',
    'version': '1.0.0',
    'summary': 'Platform Mentorship Alumni-Mahasiswa UNISA Yogyakarta',
    'description': 'Sistem mentoring berbasis web untuk menghubungkan mahasiswa dengan alumni sebagai mentor.',
    'author': 'Tim 3 - Teknologi Informasi UNISA',
    'category': 'Education',
    'depends': ['base', 'website', 'mail'],
   'data': [
    'security/ir.model.access.csv',

    'views/backend/admin_views.xml',
    'views/templates/layout.xml',
    'views/templates/login.xml',
    'views/templates/forgot_password.xml',
    'views/templates/register.xml',
    'views/templates/dashboard_mahasiswa.xml',
    'views/templates/dashboard_alumni.xml',
    'views/templates/dashboard_admin.xml',
    'views/templates/chat.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'mentorize/static/src/css/mentorize.css',
            'mentorize/static/src/js/mentorize.js',
            'mentorize/static/src/css/chat.css',
            'mentorize/static/src/js/chat.js',
            'mentorize/static/src/xml/mentorize_chat_owl.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}