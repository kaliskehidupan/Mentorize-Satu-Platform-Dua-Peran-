🎓 Mentorize
Satu Platform. Dua Peran. Mentoring yang Lebih Terarah.
Mentorize adalah platform mentoring yang mempertemukan mahasiswa dan alumni dalam satu sistem terintegrasi untuk membantu proses mentoring menjadi lebih terstruktur, terarah, dan terdokumentasi.
Platform ini dirancang untuk mengelola seluruh alur mentoring, mulai dari pengelolaan profil, rekomendasi mentor, pengajuan mentoring, penjadwalan, komunikasi, hingga pemberian feedback.
________________________________________
📌 Tentang Mentorize
Dalam proses mentoring konvensional, mahasiswa sering mengalami kesulitan dalam menemukan mentor yang sesuai, mengatur jadwal, memantau proses mentoring, dan mendokumentasikan hasil mentoring.
Mentorize hadir untuk menyelesaikan permasalahan tersebut melalui sebuah platform digital yang menyediakan alur mentoring secara terintegrasi.
🎯 Tujuan
Mentorize bertujuan untuk:
•	Mempermudah mahasiswa menemukan mentor yang sesuai.
•	Membantu alumni mengelola aktivitas mentoring.
•	Menyediakan proses pengajuan mentoring yang terstruktur.
•	Mempermudah pengaturan jadwal mentoring.
•	Menyediakan komunikasi antara mentor dan mentee.
•	Mendokumentasikan aktivitas dan hasil mentoring.
•	Membantu administrator memantau aktivitas mentoring.
•	Mengintegrasikan sistem mentoring dengan sistem manajemen berbasis Odoo.
________________________________________
👥 Role Pengguna
Mentorize memiliki beberapa role utama dengan hak akses yang berbeda.
Role	Deskripsi
👨‍🎓 Mahasiswa / Mentee	Mencari mentor, melihat rekomendasi, mengajukan mentoring, mengatur jadwal, melakukan komunikasi, dan memberikan feedback.
👨‍🏫 Alumni / Mentor	Mengelola profil, menerima atau menolak permintaan mentoring, mengatur jadwal, berkomunikasi dengan mentee, dan memantau mentoring.
🛡️ Administrator	Mengelola pengguna, memantau aktivitas sistem, mengatur data dan konfigurasi, serta mengelola hak akses.
________________________________________
✨ Fitur Utama
🔐 Authentication & Authorization
Sistem menyediakan autentikasi dan otorisasi berdasarkan role pengguna.
Fitur meliputi:
•	Login pengguna
•	Role-based access control
•	Pembatasan akses berdasarkan role
•	Manajemen session
•	Proteksi halaman berdasarkan hak akses
•	Pengelolaan akun pengguna
________________________________________
👤 Profile Management
Pengguna dapat mengelola informasi profil mereka.
Informasi yang dapat digunakan dalam profil antara lain:
•	Nama
•	Foto profil
•	Informasi akademik
•	Keahlian
•	Pengalaman
•	Minat
•	Informasi pendukung mentoring
Profil menjadi salah satu dasar dalam proses pencarian dan rekomendasi mentor.
________________________________________
🪄 Mentor Matchmaking
Mentorize menyediakan mekanisme matching untuk membantu mahasiswa menemukan mentor yang relevan.
Sistem mempertimbangkan kesesuaian antara kebutuhan mentee dengan informasi mentor.
Contoh faktor yang dapat digunakan:
•	Keahlian
•	Minat
•	Bidang mentoring
•	Pengalaman
•	Kebutuhan mahasiswa
Sistem kemudian dapat memberikan rekomendasi mentor yang paling sesuai.
Top 3 Mentor Recommendation
Mahasiswa dapat melihat beberapa mentor dengan tingkat kecocokan terbaik sebelum mengajukan mentoring.
________________________________________
📩 Mentoring Request
Mahasiswa dapat mengirimkan permintaan mentoring kepada mentor yang dipilih.
Alur umum:
Mahasiswa
    │
    ▼
Memilih Mentor
    │
    ▼
Mengirim Mentoring Request
    │
    ▼
Mentor Menerima / Menolak
    │
    ├── Ditolak
    │
    └── Diterima
          │
          ▼
      Mentoring Aktif
Status mentoring dapat digunakan untuk mengetahui perkembangan proses mentoring.
________________________________________
📅 Scheduling
Mentor dan mentee dapat mengatur jadwal sesi mentoring.
Fitur ini membantu memastikan aktivitas mentoring memiliki jadwal yang jelas dan dapat dipantau.
________________________________________
💬 Chat
Mentorize menyediakan ruang komunikasi antara mentor dan mentee.
Konsep tampilan chat:
┌────────────────┬──────────────────────────┬──────────────────┐
│                │                          │                  │
│   Contacts     │          Chat            │ Mentoring Info   │
│                │                          │                  │
│   Mentor 1     │  Message                │  Mentor          │
│   Mentor 2     │  Message                │  Schedule        │
│   Mentor 3     │  Message                │  Status           │
│                │                          │                  │
└────────────────┴──────────────────────────┴──────────────────┘
Chat digunakan untuk mendukung komunikasi selama proses mentoring.
________________________________________
⭐ Feedback
Setelah proses mentoring, mentee dapat memberikan feedback terhadap pengalaman mentoring.
Feedback dapat digunakan untuk:
•	Menilai pengalaman mentoring.
•	Mengetahui kualitas proses mentoring.
•	Menjadi bahan evaluasi mentor.
•	Membantu meningkatkan kualitas platform.
________________________________________
📊 Dashboard
Dashboard menyediakan informasi yang relevan berdasarkan role pengguna.
Mahasiswa
Menampilkan informasi seperti:
•	Rekomendasi mentor
•	Status mentoring
•	Jadwal mentoring
•	Aktivitas terbaru
Mentor
Menampilkan:
•	Mentoring aktif
•	Mentoring request
•	Jadwal
•	Aktivitas mentee
Administrator
Menampilkan informasi sistem seperti:
•	Jumlah pengguna
•	Aktivitas mentoring
•	Data mentor dan mentee
•	Status mentoring
•	Monitoring sistem
________________________________________
🔗 Integrasi Odoo
Salah satu bagian penting dari Mentorize adalah integrasi dengan Odoo sebagai sistem backend/ERP yang mendukung pengelolaan data dan proses tertentu.
Modul Odoo yang digunakan dalam pengembangan Mentorize antara lain:
•	base
•	website
•	mail
Integrasi ini memungkinkan Mentorize memanfaatkan ekosistem Odoo untuk mendukung pengelolaan data dan komunikasi.
________________________________________
🧩 Odoo Architecture
Secara sederhana, integrasi sistem dapat digambarkan sebagai berikut:
                    ┌──────────────────────┐
                    │      Mentorize       │
                    │   Mentoring System   │
                    └──────────┬───────────┘
                               │
                               │ Integration
                               ▼
                    ┌──────────────────────┐
                    │        Odoo          │
                    │      Backend         │
                    └──────────┬───────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
          Users              Mail             Website
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                         PostgreSQL
________________________________________
🔒 Security
Keamanan menjadi salah satu bagian penting dalam pengembangan Mentorize.
Sistem menerapkan beberapa mekanisme keamanan, antara lain:
Role-Based Access Control
Setiap pengguna hanya dapat mengakses fitur sesuai role dan permission yang diberikan.
User
 │
 ▼
Authentication
 │
 ▼
Role Verification
 │
 ├── Mahasiswa ──► Mentee Features
 │
 ├── Alumni ─────► Mentor Features
 │
 └── Admin ──────► Administration
ORM
Pengelolaan data menggunakan ORM (Object-Relational Mapping) sehingga aplikasi tidak perlu membangun seluruh query database secara manual.
ORM membantu:
•	Mengurangi kebutuhan raw SQL.
•	Mengelola hubungan antar model.
•	Membantu mencegah SQL Injection ketika digunakan dengan benar.
•	Menyediakan abstraction layer antara aplikasi dan database.
•	Mengikuti mekanisme permission/access control framework.
Access Control
Odoo menyediakan mekanisme access control untuk menentukan operasi yang dapat dilakukan pengguna terhadap model tertentu.
Operasi dasar yang dapat dikontrol:
Create
Read
Update
Delete
Dengan demikian, pengguna tidak otomatis memiliki akses penuh terhadap seluruh data.
________________________________________
🏗️ System Architecture
Gambaran sederhana arsitektur Mentorize:
                    ┌───────────────────┐
                    │       User        │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   Mentorize UI    │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Application Layer │
                    │                   │
                    │ Authentication    │
                    │ Matching          │
                    │ Mentoring         │
                    │ Scheduling        │
                    │ Chat              │
                    │ Feedback          │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   Odoo Backend    │
                    └─────────┬─────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │    PostgreSQL     │
                    └───────────────────┘
________________________________________
🛠️ Technology Stack
Technology	Usage
Python	Backend / Odoo
Odoo 17	Backend framework & system integration
PostgreSQL	Database
OWL	Odoo frontend components
XML	Odoo views & configuration
JavaScript	Frontend interaction
HTML / CSS	User interface
Git	Version control
GitHub	Repository & collaboration
SMTP	Email communication
SSO	Authentication integration
________________________________________
📁 Project Structure
Struktur project secara umum:
mentorize/
│
├── addons/
│   └── mentorize/
│       ├── models/
│       ├── views/
│       ├── security/
│       ├── data/
│       ├── static/
│       │   └── src/
│       ├── controllers/
│       ├── wizard/
│       ├── demo/
│       ├── __init__.py
│       └── __manifest__.py
│
├── config/
│
├── documentation/
│
├── requirements.txt
│
└── README.md
Struktur aktual dapat berbeda tergantung versi source code dan konfigurasi deployment.
________________________________________
🚀 Installation
1. Clone Repository
git clone https://github.com/USERNAME/mentorize.git
cd mentorize
2. Siapkan Environment
Pastikan environment memiliki:
•	Python
•	PostgreSQL
•	Odoo 17
•	Git
Disarankan menggunakan virtual environment Python.
python -m venv venv
Aktifkan environment:
Windows
venv\Scripts\activate
Linux / macOS
source venv/bin/activate
________________________________________
3. Install Dependencies
pip install -r requirements.txt
________________________________________
4. Konfigurasi Database
Buat database PostgreSQL untuk Mentorize dan sesuaikan konfigurasi Odoo.
Contoh konfigurasi:
[options]

db_host = localhost
db_port = 5432
db_user = odoo
db_password = your_password

addons_path = addons
________________________________________
5. Jalankan Odoo
Contoh:
python odoo-bin -c odoo.conf
Kemudian akses aplikasi melalui browser:
http://localhost:8069
________________________________________
⚙️ Configuration
Beberapa konfigurasi yang perlu disiapkan sebelum menjalankan sistem:
Database
PostgreSQL
├── Host
├── Port
├── Database
├── Username
└── Password
SMTP
Digunakan untuk kebutuhan pengiriman email dari sistem.
SSO
Jika menggunakan autentikasi SSO, konfigurasi credential dan client secret perlu disiapkan pada environment/configuration.
Jangan menyimpan password, API key, client secret, atau credential lainnya secara langsung di repository.
________________________________________
🧪 Testing
Pengujian sistem dilakukan untuk memastikan setiap fungsi berjalan sesuai kebutuhan.
Area pengujian meliputi:
•	Authentication
•	Authorization
•	Profile Management
•	Mentor Matching
•	Mentoring Request
•	Scheduling
•	Chat
•	Feedback
•	Dashboard
•	Odoo Integration
•	Access Control
________________________________________
🔄 Business Flow
Alur utama Mentorize:
                    START
                      │
                      ▼
               User Login / SSO
                      │
                      ▼
                Role Detection
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
      Mahasiswa                 Alumni
          │                       │
          ▼                       ▼
   Lengkapi Profil          Lengkapi Profil
          │                       │
          ▼                       │
   Mentor Matching                │
          │                       │
          ▼                       │
   Rekomendasi Mentor             │
          │                       │
          ▼                       │
   Kirim Request ─────────────────┘
          │
          ▼
      Mentor Review
          │
       ┌──┴──┐
       ▼     ▼
    Reject  Accept
               │
               ▼
        Schedule Mentoring
               │
               ▼
             Chat
               │
               ▼
       Mentoring Session
               │
               ▼
           Feedback
               │
               ▼
              END
________________________________________
🎯 Project Goals
Mentorize dikembangkan untuk menghasilkan sistem mentoring yang:
•	Terstruktur — setiap proses mentoring memiliki alur yang jelas.
•	Terintegrasi — data dan proses dapat dikelola dalam satu ekosistem.
•	Personalized — mahasiswa mendapatkan rekomendasi mentor berdasarkan kebutuhan.
•	Secure — akses data dibatasi berdasarkan role dan permission.
•	Scalable — sistem dirancang agar dapat dikembangkan untuk kebutuhan yang lebih besar.
________________________________________
👨‍💻 Development Team
Mentorize dikembangkan sebagai project sistem informasi dengan pembagian peran dalam tim.
Project Manager:
Sahrine Estari Ditara
Peran dalam project meliputi:
•	Project Management
•	System Analysis
•	System Design
•	Backend Development
•	Odoo Integration
•	Database Design
•	Security Configuration
•	Testing
•	Documentation
________________________________________
📚 Documentation
Dokumentasi project mencakup:
•	Software Requirements Specification (SRS)
•	Business Process
•	System Architecture
•	Database Design
•	UI/UX Design
•	API / Integration Documentation
•	Security Configuration
•	Testing Documentation
•	Deployment Documentation
________________________________________
📸 Screenshots
Tambahkan screenshot aplikasi di bagian ini untuk memperlihatkan tampilan Mentorize.
Contoh:
docs/
└── screenshots/
    ├── login.png
    ├── dashboard.png
    ├── mentor-matching.png
    ├── mentoring-request.png
    ├── chat.png
    └── admin-dashboard.png
Kemudian tampilkan pada README:
![Login](docs/screenshots/login.png)

![Dashboard](docs/screenshots/dashboard.png)

![Mentor Matching](docs/screenshots/mentor-matching.png)
________________________________________
🔮 Future Development
Beberapa pengembangan yang dapat dilakukan:
•	Peningkatan algoritma mentor matching.
•	Real-time notification.
•	Real-time chat.
•	Video conference integration.
•	Mobile application.
•	Advanced analytics dashboard.
•	Recommendation system berbasis machine learning.
•	Integrasi kalender.
•	Automated mentoring reports.
•	Pengembangan API untuk integrasi dengan sistem eksternal.
________________________________________
📄 License
Project ini dikembangkan untuk kebutuhan pengembangan dan pembelajaran sistem informasi.
Lisensi penggunaan dan distribusi dapat ditentukan sesuai kebutuhan project.
________________________________________
⭐ Mentorize
Satu Platform. Dua Peran. Mentoring yang Lebih Terarah.
Mentorize menghubungkan mahasiswa dan alumni dalam satu platform untuk menciptakan proses mentoring yang lebih mudah, terstruktur, dan terdokumentasi.

