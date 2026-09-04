# Chạy MinIO dạng service độc lập trên Windows

1. Tải `minio.exe` từ trang MinIO chính thức và đặt vào, ví dụ, `C:\minio\minio.exe`.
2. Tạo thư mục dữ liệu, ví dụ `C:\minio-data`.
3. Trong PowerShell (môi trường demo), đặt hai biến bí mật riêng và chạy:

```powershell
$env:MINIO_ROOT_USER = 'minioadmin'
$env:MINIO_ROOT_PASSWORD = '<mat-khau-dai-va-rieng>'
C:\minio\minio.exe server C:\minio-data --console-address ":9001"
```

4. Mở `http://localhost:9001`, đăng nhập, rồi tạo bucket `job-portal-documents` nếu ứng dụng chưa tự tạo.
5. Đặt các biến sau trong `.env` (không commit mật khẩu):

```env
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=<mat-khau-dai-va-rieng>
MINIO_BUCKET=job-portal-documents
MINIO_SECURE=false
```

Để chạy nền như Windows Service, dùng NSSM hoặc Task Scheduler để gọi đúng câu lệnh ở bước 3 với một tài khoản dịch vụ hạn chế. Khi triển khai HTTPS, đặt `MINIO_SECURE=true` và dùng endpoint TLS. PostgreSQL chỉ nhận object key, không bao giờ nhận file binary.
