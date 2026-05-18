# Mentorize - Update Auth, Profile, Dashboard Mahasiswa

Perubahan utama:

1. Route lama `/mentorize/...` tetap bisa dipakai, tetapi route utama sudah dibuat lebih langsung:
   - `/` landing page sebelum login
   - `/login`
   - `/register`
   - `/forgot-password`
   - `/dashboard`
   - `/profile`
   - `/profile/edit`
   - `/mentors`
   - `/alumni/dashboard`
   - `/admin/dashboard`

2. Tampilan auth, landing page, dashboard mahasiswa, profil mahasiswa, cari mentor, dashboard alumni, dan admin dibuat ulang supaya lebih mendekati desain Figma.

3. Interaksi pemilihan role login/register sudah memakai OWL component:
   - `static/src/js/mentorize_owl.js`
   - `static/src/xml/mentorize_components.xml`

4. Animasi ditambahkan melalui CSS dan JS:
   - fade/slide saat halaman masuk
   - hover animation pada card/button
   - loading state saat submit form
   - counter animation pada dashboard
   - transition sederhana saat berpindah halaman

5. Model dan controller dirapikan:
   - Register menyimpan NIM/KAPA ke `res.users` dan profil terkait.
   - Dashboard mahasiswa mengambil rekomendasi mentor, request pending, mentoring aktif, jadwal, riwayat, dan progress.
   - Profil mahasiswa bisa tampil dan diedit.
   - Request mentor sederhana tersedia dari halaman `/mentors`.

6. Security/access diperbaiki agar tidak hanya berisi akses public.

Cara update di Odoo:

```bash
python odoo-bin -c odoo.conf -u mentorize --dev=assets
```

Setelah update, buka:

```text
http://localhost:8069/
http://localhost:8069/login
http://localhost:8069/dashboard
```

Catatan:
- Fitur chat, sesi lengkap, dan riwayat detail masih placeholder karena fokus update ini adalah bagian Saiful: Auth, Profile, Dashboard Mahasiswa, dan landing page sebelum login.
- Jika asset belum berubah, aktifkan developer mode lalu clear asset/cache browser, atau restart Odoo dan update module ulang.
