# Pangan Pintar API — Integration Guide

Panduan integrasi Pangan Pintar API untuk tim Web (React / Next.js / Vue / Vanilla JS). Berisi sample code siap copy-paste, error handling pattern, dan best practices.

**Untuk:** Tim Web Pangan Pintar
**Maintained by:** Tim KDN — SM Firman & ML Ops Kelin

---

## 1. Quick Start (5 menit)

### Step 1 — Pastikan env mu di-allow CORS

- Saat ini whitelisted: `localhost:3000`, `localhost:5173`, `localhost:8080` plus 127.0.0.1 variant
- Kalau pakai port lain atau deployed domain, kontak maintainer

### Step 2 — Test connection dengan curl atau Postman

```bash
curl https://firmanfadilah-pangan-pintar-api.hf.space/health
```

Harus return `{"status":"healthy",...}`.

### Step 3 — Fetch test prediksi dari frontend

```javascript
const res = await fetch(
  "https://firmanfadilah-pangan-pintar-api.hf.space/api/v1/predict",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      commodity: "Beras",
      province: "Aceh",
      target_week: "2026-01-12",
    }),
  },
);
const data = await res.json();
console.log(data); // { predicted_price: 15121.15, ... }
```

Kalau muncul data prediksi, integrasi sudah jalan. Lanjut ke section berikutnya untuk code yang lebih lengkap.

---

## 2. Setup Environment Variables

Buat file `.env.local` di root project Next.js / React:

```
NEXT_PUBLIC_API_BASE_URL=https://firmanfadilah-pangan-pintar-api.hf.space
```

Untuk Vite / Create React App:

```
VITE_API_BASE_URL=https://firmanfadilah-pangan-pintar-api.hf.space
```

Kemudian akses di code:

```javascript
// Next.js
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL;

// Vite
const API_BASE = import.meta.env.VITE_API_BASE_URL;
```

**Kenapa pakai env variable:** supaya kalau pindah environment (staging, production), tinggal ubah env file, tidak perlu ubah code.

---

## 3. Sample Code — React Hooks (Recommended)

Hooks ini bisa di-copy ke folder `hooks/` di project mu.

### 3.1 `usePrediction.js` — Hook untuk fetch prediksi

```javascript
import { useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://firmanfadilah-pangan-pintar-api.hf.space";

export function usePrediction() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const predict = async ({ commodity, province, target_week }) => {
    setLoading(true);
    setError(null);
    setData(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ commodity, province, target_week }),
      });

      if (!res.ok) {
        const errBody = await res.json();
        // Handle different error shapes
        const errorMsg =
          errBody.detail?.message ||
          errBody.detail?.[0]?.msg ||
          "Gagal memprediksi harga";
        throw new Error(errorMsg);
      }

      const result = await res.json();
      setData(result);
      return result;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setLoading(false);
    }
  };

  return {
    predict,
    loading,
    error,
    data,
    reset: () => {
      setData(null);
      setError(null);
    },
  };
}
```

### 3.2 `useCommodities.js` — Hook untuk fetch list komoditas

```javascript
import { useState, useEffect } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://firmanfadilah-pangan-pintar-api.hf.space";

export function useCommodities() {
  const [commodities, setCommodities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/commodities`)
      .then((res) => {
        if (!res.ok) throw new Error("Gagal fetch list komoditas");
        return res.json();
      })
      .then((data) => setCommodities(data.commodities))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { commodities, loading, error };
}
```

### 3.3 `useProvinces.js` — Hook untuk fetch list provinsi

```javascript
import { useState, useEffect } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://firmanfadilah-pangan-pintar-api.hf.space";

export function useProvinces() {
  const [provinces, setProvinces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/provinces`)
      .then((res) => {
        if (!res.ok) throw new Error("Gagal fetch list provinsi");
        return res.json();
      })
      .then((data) => setProvinces(data.provinces))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { provinces, loading, error };
}
```

---

## 4. Sample Component — Form Prediksi

Component lengkap yang pakai 3 hooks di atas, untuk form prediksi dengan dropdown komoditas dan provinsi.

```jsx
import { useState } from "react";
import { usePrediction } from "./hooks/usePrediction";
import { useCommodities } from "./hooks/useCommodities";
import { useProvinces } from "./hooks/useProvinces";

export default function PredictionForm() {
  const { commodities, loading: loadingCom } = useCommodities();
  const { provinces, loading: loadingProv } = useProvinces();
  const { predict, loading, error, data, reset } = usePrediction();

  const [form, setForm] = useState({
    commodity: "",
    province: "",
    target_week: "",
  });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.commodity || !form.province || !form.target_week) {
      alert("Mohon lengkapi semua field");
      return;
    }
    try {
      await predict(form);
    } catch (e) {
      // Error sudah di-set di hook, tidak perlu apa-apa di sini
    }
  };

  return (
    <div className="prediction-form">
      <h2>Prediksi Harga Pangan</h2>

      <form onSubmit={handleSubmit}>
        <div>
          <label>Komoditas</label>
          <select
            name="commodity"
            value={form.commodity}
            onChange={handleChange}
            disabled={loadingCom}
          >
            <option value="">-- Pilih Komoditas --</option>
            {commodities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label>Provinsi</label>
          <select
            name="province"
            value={form.province}
            onChange={handleChange}
            disabled={loadingProv}
          >
            <option value="">-- Pilih Provinsi --</option>
            {provinces.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label>Minggu Target</label>
          <input
            type="date"
            name="target_week"
            value={form.target_week}
            onChange={handleChange}
            min="2023-12-25"
            max="2026-02-16"
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Memprediksi..." : "Prediksi"}
        </button>

        {error && (
          <div className="error">
            <strong>Error:</strong> {error}
            <button type="button" onClick={reset}>
              Tutup
            </button>
          </div>
        )}

        {data && (
          <div className="result">
            <h3>Hasil Prediksi</h3>
            <p>
              Komoditas: <strong>{data.commodity}</strong>
            </p>
            <p>
              Provinsi: <strong>{data.province}</strong>
            </p>
            <p>
              Minggu: <strong>{data.target_week}</strong>
            </p>
            <p>
              Harga Prediksi:{" "}
              <strong>Rp {data.predicted_price.toLocaleString("id-ID")}</strong>
            </p>
            <p className="meta">
              Model: {data.model} | Predicted at: {data.predicted_at}
            </p>
          </div>
        )}
      </form>
    </div>
  );
}
```

---

## 5. Sample Code — Plain Fetch (Non-React)

Untuk yang tidak pakai React, contoh fetch biasa:

```javascript
async function predictPrice(commodity, province, targetWeek) {
  const API_BASE = "https://firmanfadilah-pangan-pintar-api.hf.space";

  try {
    const res = await fetch(`${API_BASE}/api/v1/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commodity: commodity,
        province: province,
        target_week: targetWeek,
      }),
    });

    if (!res.ok) {
      const errBody = await res.json();
      throw new Error(errBody.detail?.message || "Prediction failed");
    }

    return await res.json();
  } catch (e) {
    console.error("Prediksi gagal:", e.message);
    throw e;
  }
}

// Usage
predictPrice("Beras", "Aceh", "2026-01-12")
  .then((result) => console.log(result))
  .catch((e) => console.error(e));
```

---

## 6. Sample Code — Axios (Alternatif)

Kalau project sudah pakai axios:

```javascript
import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL,
  timeout: 30000, // 30 detik timeout untuk cold start HF Space
});

export async function getPrediction(commodity, province, targetWeek) {
  try {
    const { data } = await api.post("/api/v1/predict", {
      commodity,
      province,
      target_week: targetWeek,
    });
    return data;
  } catch (err) {
    if (err.response) {
      const msg = err.response.data?.detail?.message || "Prediksi gagal";
      throw new Error(msg);
    }
    throw err;
  }
}

export async function getCommodities() {
  const { data } = await api.get("/api/v1/commodities");
  return data.commodities;
}

export async function getProvinces() {
  const { data } = await api.get("/api/v1/provinces");
  return data.provinces;
}
```

---

## 7. Error Handling Pattern

API mengembalikan beberapa shape error berbeda. Gunakan helper ini untuk extract message:

```javascript
function extractErrorMessage(errorBody) {
  // Shape 1: { detail: { error: '...', message: '...' } } - business logic error
  if (errorBody.detail?.message) {
    return errorBody.detail.message;
  }

  // Shape 2: { detail: [{ type: '...', loc: [...], msg: '...' }] } - Pydantic validation
  if (Array.isArray(errorBody.detail) && errorBody.detail.length > 0) {
    return errorBody.detail[0].msg;
  }

  // Shape 3: { detail: 'string error' } - simple
  if (typeof errorBody.detail === "string") {
    return errorBody.detail;
  }

  return "Terjadi kesalahan tidak terduga";
}
```

---

## 8. Tips & Best Practices

### 8.1 Cache list komoditas dan provinsi

`/commodities` dan `/provinces` tidak berubah, fetch sekali saja saat app load. Tidak perlu fetch ulang setiap user buka form.

Bisa pakai state management (Zustand, Redux) atau context React untuk simpan, atau cache di `localStorage` dengan TTL 1 hari.

### 8.2 Debounce input user

Kalau ada UI yang otomatis predict saat user ganti dropdown, **debounce 500ms** supaya tidak spam API.

```javascript
import { useEffect } from "react";

function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debouncedValue;
}
```

### 8.3 Handle cold start (HF Spaces free tier)

HuggingFace Spaces free tier akan **idle setelah ~30 menit tidak ada request**. Request pertama setelah idle akan butuh **5-15 detik** untuk warm-up.

Solusi: kasih loading state yang jelas, plus tooltip "Memuat model... mohon tunggu" untuk first request.

```jsx
{
  loading && <div>Memprediksi... (kalau lama, server lagi warm-up)</div>;
}
```

### 8.4 Format harga sesuai locale Indonesia

Gunakan `toLocaleString` untuk display Rupiah:

```javascript
const formatted = (15121.15).toLocaleString("id-ID", {
  style: "currency",
  currency: "IDR",
  minimumFractionDigits: 0,
});
// "Rp 15.121"
```

### 8.5 Validasi target_week di frontend

Cek di client side juga supaya UX lebih cepat (tidak perlu round-trip ke server):

```javascript
function isValidTargetWeek(dateStr) {
  const minDate = new Date("2023-12-25");
  const maxDate = new Date("2026-02-16");
  const target = new Date(dateStr);
  return target >= minDate && target <= maxDate;
}
```

---

## 9. Common Issues

### "CORS error: blocked by CORS policy"

**Penyebab:** Origin frontend tidak ada di whitelist backend.

**Solusi:** Kontak maintainer (Firman) untuk add domain ke `CORS_ORIGINS` di HuggingFace Space. Sertakan info:

- URL frontend (misal `https://pangan-pintar.vercel.app`)
- Apakah ini dev, staging, atau production

### "Failed to fetch"

**Penyebab:** Network issue, atau backend down, atau cold start sedang berlangsung.

**Solusi:**

1. Cek backend hidup: ping `https://firmanfadilah-pangan-pintar-api.hf.space/health`
2. Kalau response 200, ulangi request (mungkin cold start)
3. Kalau response timeout, hubungi maintainer

### "Value error, Commodity 'X' is not supported"

**Penyebab:** Nama komoditas salah (typo atau format berbeda).

**Solusi:** Gunakan list dari `/api/v1/commodities`, jangan hardcode. Case-sensitive, perhatikan kapitalisasi (contoh: `"Beras"` valid, `"beras"` invalid).

### "Target week X is not predictable"

**Penyebab:** target_week kurang dari 52 minggu setelah data history paling awal, atau melebihi data terakhir.

**Solusi:** Pakai range valid 2023-12-25 sampai 2026-02-16, atau pakai input date dengan `min` dan `max`.

### Response lambat (lebih dari 5 detik)

**Penyebab:** Cold start HF Spaces.

**Solusi:** Tampilkan loading indicator. Untuk burst traffic critical (misal saat demo Sprint Review), bisa ping `/health` setiap 10 menit untuk keep-alive.

---

## 10. Kontak

Untuk request fitur baru, bug report, atau request CORS whitelist baru, hubungi:

**Maintainer Backend ML Ops:** Firman Fadilah
**Channel:** Slack Tim KDN
**Capstone:** Pangan Pintar — Infinite Learning AI Dev B10
