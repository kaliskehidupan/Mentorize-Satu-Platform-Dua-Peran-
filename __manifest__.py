{
    'name': 'Mentoring System',
    'version': '1.0',
    'summary': 'Platform Mentoring Alumni & Mahasiswa',
    'category': 'Education',
    'author': 'Tim 3',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',   
        'views/mentoring_views.xml',
    ],
    'installable': True,
    'application': True,
}