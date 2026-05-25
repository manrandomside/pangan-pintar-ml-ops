# Pangan Pintar API — Maintenance Guide

Dokumentasi internal untuk tim ML Ops Pangan Pintar. Berisi cara update artifacts, redeploy, monitoring, dan troubleshooting.

**Audience:** Internal ML Ops Team (Kelin, Firman)
**Maintained by:** Firman Fadilah

---

## 1. Architecture Overview

### Stack Production

- **Backend Framework:** FastAPI 0.115.0
- **Python:** 3.13
- **ML Framework:** XGBoost 3.2.0
- **Data:** scikit-learn 1.5.2, pandas 2.2.3, numpy 2.1.2
- **Server:** Uvicorn (async ASGI)
- **Containerization:** Docker (multi-stage build)

### Hosting

- **Production:** HuggingFace Spaces (Docker SDK, CPU basic free tier)
- **Hardware:** 2 vCPU, 16 GB RAM, persistent storage included
- **Container Port:** 7860 (HuggingFace default)

### Source Code

- **GitHub Repo:** https://github.com/manrandomside/pangan-pintar-ml-ops
- **HF Space:** https://huggingface.co/spaces/firmanfadilah/pangan-pintar-api
- **Default Branch:** main
- **Git LFS:** active untuk file `*.pkl`

### Local Development

- **Venv path:** `PanganPintar-ML-Ops/venv/`
- **Start dev server:** `uvicorn main:app --reload`
- **Default port:** 8000

---

## 2. Update Workflow

### 2.1 Update Model Artifacts (yang paling sering)

**Use case:** Tim ML Engineer (Upi, Augustian) re-train model dengan data baru atau bug fix.

**Steps:**

1. **Tim ML Engineer share `artifacts_fresh.zip`** (atau equivalent)
   - Berisi: 10 file `xgb_*.pkl`, `metadata.json`, `walk_forward_predictions.csv`, `weekly_prices.csv`
   - Total size sekitar 25-30 MB

2. **Backup folder artifacts saat ini** (di local laptop):

   ```powershell
   ren artifacts artifacts_backup_YYYYMMDD
   ```

   Format tanggal: `artifacts_backup_20260601` misalnya.

3. **Extract zip baru ke folder `artifacts/`:**
   - Buat folder kosong `artifacts/`
   - Extract isi zip ke folder tersebut
   - Verify ada 13 file (10 pkl + 3 supporting file)

4. **Sanity check di local sebelum push:**

   ```powershell
   uvicorn main:app --reload
   ```

   Lalu test di `http://localhost:8000/docs`. Test minimal 3 komoditas:
   - Beras Aceh 2026-01-12 (expected ~15.000)
   - Cabai Rawit DKI Jakarta 2026-01-19 (expected 40.000-100.000)
   - Daging Sapi Bali 2026-01-26 (expected 130.000-160.000)

5. **Kalau prediksi reasonable, commit & push:**

   ```bash
   git add artifacts/
   git commit -m "update: model artifacts vX (date)"
   git push origin main
   git push space main
   ```

6. **Tunggu HF Space auto-rebuild** (3-7 menit)

7. **Verify production endpoint:**
   - Buka `https://firmanfadilah-pangan-pintar-api.hf.space/docs`
   - Test prediksi yang sama dengan local
   - Pastikan hasilnya match dengan local

8. **Done.** Update production endpoint dengan model baru.

### 2.2 Update Code (bug fix, fitur baru)

**Steps:**

1. **Buat branch baru:**

   ```bash
   git checkout -b fix/cors-update
   ```

2. **Edit code, test di local:**

   ```bash
   uvicorn main:app --reload
   ```

3. **Commit perubahan:**

   ```bash
   git add .
   git commit -m "fix: update CORS to include staging domain"
   ```

4. **Merge ke main, push:**

   ```bash
   git checkout main
   git merge fix/cors-update
   git push origin main
   git push space main
   ```

5. **HF Space auto-rebuild**. Tunggu, verify.

### 2.3 Update Environment Variables di HF Space

**Use case:** Update `CORS_ORIGINS`, add API key, dll.

**Steps:**

1. Buka https://huggingface.co/spaces/firmanfadilah/pangan-pintar-api/settings
2. Scroll ke **Variables and secrets**
3. Edit value variable yang dimaksud (atau add baru)
4. Klik Save
5. Space auto-restart (1-3 menit)
6. Verify dengan test endpoint

**Penting:**

- **Variables** = public (terlihat di Space settings, bisa dipakai untuk URL, port, dll)
- **Secrets** = private (untuk API keys, database password, dll, tidak terlihat)

Untuk Pangan Pintar saat ini, semua config (termasuk `CORS_ORIGINS`) di-set sebagai Variables karena tidak ada sensitive data.

---

## 3. Monitoring

### 3.1 Build Logs

URL: https://huggingface.co/spaces/firmanfadilah/pangan-pintar-api?logs=build

Setiap kali `git push space main`, akan trigger build. Logs menampilkan:

- Docker layer caching
- pip install dependencies
- Copy code & artifacts
- Container startup

**Kalau build gagal,** error akan muncul di logs ini. Biasanya di langkah `pip install` (dependency conflict) atau `COPY` (file path issue).

### 3.2 Runtime Logs

URL: https://huggingface.co/spaces/firmanfadilah/pangan-pintar-api?logs=container

Logs application yang sedang jalan. Menampilkan:

- Startup logs (load model, init service)
- Setiap incoming request (method, path, status, latency)
- Error stack trace kalau ada exception

**Tips:** Pin tab ini di browser saat ada user testing intensive, untuk monitor request real-time.

### 3.3 HuggingFace Analytics

URL: https://huggingface.co/spaces/firmanfadilah/pangan-pintar-api/analytics

Menampilkan:

- Total visit per hari
- Unique visitor
- Traffic source (referrer)

Kebanyakan analytics traffic akan dari `/docs` (Swagger UI) untuk debugging tim. Traffic dari Web app real akan masuk via API endpoint langsung, jadi tidak selalu ke-record di sini.

### 3.4 Uptime Monitoring (Optional)

Untuk produksi sungguhan, recommend pakai uptime checker eksternal:

- **UptimeRobot** (free, 50 monitors): ping `/health` setiap 5 menit
- **Better Uptime** (free tier)
- **Healthchecks.io** (free tier)

Konfigurasi: ping URL `https://firmanfadilah-pangan-pintar-api.hf.space/health`. Alert kalau response bukan 200.

---

## 4. Rollback Strategy

Kalau deploy baru ada bug, rollback ke versi sebelumnya:

### 4.1 Rollback via Git Reset

```bash
# Lihat history commit
git log --oneline -n 10

# Reset ke commit sebelum bug (misal commit hash abc1234)
git reset --hard abc1234

# Force push ke HF Space
git push space main --force
```

**Tunggu auto-rebuild**, lalu verify.

### 4.2 Rollback Cara Alternatif — Via HF Space UI

1. Buka https://huggingface.co/spaces/firmanfadilah/pangan-pintar-api/tree/main
2. Klik file yang bermasalah
3. Klik tombol "History" atau "View earlier versions"
4. Pilih versi sebelum bug
5. Click "Restore to this version"

Cara ini hanya bisa untuk file kecil (bukan `.pkl` yang via LFS).

### 4.3 Rollback Model Artifacts

Kalau model baru hasilnya buruk, kembalikan ke folder backup:

```powershell
ren artifacts artifacts_broken
ren artifacts_backup_YYYYMMDD artifacts

git add artifacts/
git commit -m "rollback: revert model to v1 (broken vN)"
git push origin main
git push space main
```

---

## 5. Common Issues & Fixes

### 5.1 "Build error: failed to install dependencies"

**Cause:** pip dependency conflict atau version not found.

**Fix:**

- Cek `requirements.txt`. Apakah ada version yang tidak compatible?
- Test di local dulu: `pip install -r requirements.txt --dry-run`
- Pin version yang lebih konservatif

### 5.2 "Out of memory" saat startup

**Cause:** Load 10 model + 55K rows CSV butuh memory. Tier free HF biasanya cukup (16 GB), tapi kalau ada memory leak bisa hit limit.

**Fix:**

- Cek di logs apakah ada model yang load gagal
- Restart container (push commit kosong: `git commit --allow-empty -m "restart"`)
- Kalau sering OOM, pertimbangkan upgrade ke tier yang lebih besar

### 5.3 "Predicted price negative atau ekstrim"

**Cause:** Feature engineering mismatch antara training dan inference. Lihat checklist debugging di section 6.

**Fix:** Bandingkan output `inspect_artifacts.py` di local dengan output sanity check di Colab. Trace feature mana yang beda.

### 5.4 "CORS error" dari frontend

**Cause:** Origin frontend belum di-whitelist.

**Fix:** Add domain ke `CORS_ORIGINS` di HF Space settings (lihat section 2.3).

### 5.5 "503 Service Unavailable" dari HF Space

**Cause:** Space sedang restart, atau idle (untuk free tier).

**Fix:**

- Tunggu 30-60 detik, refresh
- Untuk free tier, pertimbangkan keep-alive ping setiap 25 menit (sebelum 30 menit idle limit)

---

## 6. Debugging Checklist saat Hasil Prediksi Salah

Kalau di production hasil prediksi mencurigakan (negatif, atau jauh dari expected range):

1. **Compare dengan local backend.**
   - Stop production temporarily kalau perlu
   - Run `uvicorn main:app --reload` di local
   - Test endpoint yang sama
   - Bandingkan hasil

2. **Cek versi XGBoost.**
   - Local: `python -c "import xgboost; print(xgboost.__version__)"`
   - Production: lihat log build atau `requirements.txt`
   - Harus **identik** (saat ini 3.2.0)

3. **Cek model file integrity.**
   - Bandingkan size file `.pkl` di local vs di Space
   - Bisa download dari Space via web UI, compare byte-by-byte kalau perlu

4. **Cek feature engineering.**
   - Jalankan script di local:
     ```bash
     python scripts/inspect_artifacts.py
     ```
   - Bandingkan feature value Beras Aceh 2026-01-12 dengan sanity check Colab
   - Setiap feature harus match desimal demi desimal

5. **Cek environment variable.**
   - Variable di HF Space mungkin tidak ter-set dengan benar
   - Test endpoint `/health`, pastikan service masih hidup

---

## 7. Disaster Recovery

### 7.1 Skenario: GitHub repo terhapus

**Recovery:**

- Re-create repo di GitHub dengan nama yang sama
- Push dari local: `git push origin main`
- Update remote di HF Space settings kalau pakai auto-sync

### 7.2 Skenario: HF Space terhapus / di-suspend

**Recovery:**

- Create Space baru dengan nama sama
- Push dari local: `git push space main --force`
- Re-configure CORS_ORIGINS environment variable
- Update URL di docs jika berubah

### 7.3 Skenario: Local laptop crash, kode hilang

**Recovery:**

- Clone dari GitHub: `git clone https://github.com/manrandomside/pangan-pintar-ml-ops.git`
- Install dependencies: `pip install -r requirements.txt`
- Setup venv ulang

### 7.4 Skenario: Semua model artifacts hilang

**Recovery:**

- Re-train dari notebook capstone (di Colab)
- Atau download dari GitHub repo (LFS): `git lfs pull`

---

## 8. Future Improvements (Backlog)

Beberapa improvement yang bisa dilakukan kalau ada waktu / setelah capstone:

1. **CI/CD pipeline:** GitHub Actions untuk auto-deploy ke HF Space saat merge ke main
2. **Caching layer:** Redis untuk cache result prediksi yang sering diminta
3. **Monitoring tools:** Sentry untuk error tracking, Grafana untuk metrics
4. **Rate limiting:** slowapi atau Cloudflare buat anti-abuse
5. **API versioning:** persiapan untuk v2 (kalau ada perubahan major)
6. **Model versioning:** track versi model dengan MLflow atau DVC
7. **A/B testing:** rute traffic ke 2 model versi untuk compare performance
8. **Auto-update data:** scheduled job untuk fetch data harga terbaru dari PIHPS dan re-train

---

## 9. Handover Notes

Jika ada pergantian person in charge ML Ops, dokumen ini berisi semua yang perlu diketahui. Plus:

- **Credentials yang dipakai:**
  - GitHub: pakai akun `manrandomside` (handover via SSH key atau buat new collaborator)
  - HuggingFace: pakai akun `firmanfadilah` (handover via add collaborator)
  - Kaggle: tidak dipakai lagi setelah dataset di-takedown (2026)

- **Folder backup di local laptop:**
  - `artifacts_old/` — model versi awal (dengan data leakage)
  - `artifacts_old_v2/` — model versi tengah
  - `artifacts/` — model production current

- **Notebook training:**
  - File: `Pangan_Pintar_Training_NoKaggle.ipynb`
  - Lokasi: shared di Drive tim KDN
  - Cara pakai: upload ke Colab, upload `weekly_prices.csv`, Run all

---

## 10. Contact

**Maintainer:** Firman Fadilah
**Role:** Scrum Master + ML Ops Tim KDN
**Capstone:** Pangan Pintar — Infinite Learning AI Dev B10
**Sprint Review 3:** Mei 2026
