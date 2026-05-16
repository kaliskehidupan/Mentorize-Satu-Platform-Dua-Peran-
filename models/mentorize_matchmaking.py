from odoo import models, fields, api

class MentorizeMatchmaking(models.Model):
    _name = 'mentorize.matchmaking'
    _description = 'Matchmaking Mentor-Mentee'
    _order = 'score desc'

    mahasiswa_id = fields.Many2one('mentorize.mahasiswa', string='Mahasiswa', required=True, ondelete='cascade')
    alumni_id = fields.Many2one('mentorize.alumni', string='Alumni/Mentor', required=True, ondelete='cascade')
    score = fields.Float(string='Skor Kecocokan', default=0.0)
    skill_match = fields.Integer(string='Skill Cocok', default=0)
    minat_match = fields.Integer(string='Minat Cocok', default=0)
    is_recommended = fields.Boolean(string='Direkomendasikan', default=False)
    tanggal_generate = fields.Datetime(string='Tanggal Generate', default=fields.Datetime.now)

    @api.model
    def generate_matchmaking(self, mahasiswa_id):
        """Generate rekomendasi mentor untuk mahasiswa berdasarkan skill & minat"""
        mahasiswa = self.env['mentorize.mahasiswa'].browse(mahasiswa_id)
        if not mahasiswa.exists():
            return []

        # Hapus matchmaking lama
        self.search([('mahasiswa_id', '=', mahasiswa_id)]).unlink()

        # Ambil semua alumni yang tersedia dan terverifikasi
        alumni_list = self.env['mentorize.alumni'].search([
            ('ketersediaan', '=', 'available'),
            ('is_verified', '=', True),
            ('slot_mentoring', '>', 0),
        ])

        results = []
        mahasiswa_skills = mahasiswa.skill_ids.ids
        mahasiswa_minats = mahasiswa.minat_ids.ids

        for alumni in alumni_list:
            alumni_skills = alumni.skill_ids.ids

            # Hitung kecocokan skill
            skill_match = len(set(mahasiswa_skills) & set(alumni_skills))

            # Hitung kecocokan minat (alumni skill vs mahasiswa minat)
            minat_match = len(set(mahasiswa_minats) & set(alumni_skills))

            # Hitung skor total: skill lebih berbobot
            score = (skill_match * 2) + (minat_match * 1.5) + (alumni.rating * 0.5)

            if score > 0 or alumni.rating > 0:
                matchmaking = self.create({
                    'mahasiswa_id': mahasiswa_id,
                    'alumni_id': alumni.id,
                    'score': score,
                    'skill_match': skill_match,
                    'minat_match': minat_match,
                    'is_recommended': score >= 3.0,
                })
                results.append(matchmaking)

        return results
