# EC2로 새 파일만 전송 (크롤링 없이 sync만)
# 사용법: powershell -ExecutionPolicy Bypass -File sync_only.ps1

$EC2_HOST    = "ubuntu@107.22.8.250"
$EC2_KEY     = "C:\Users\User\Desktop\CRAI\ku-hys-01-key.pem"
$EC2_IMG_DIR = "/home/ubuntu/CRAI/backend/data/images"
$EC2_DB_DIR  = "/home/ubuntu/CRAI/backend/db"

$ROOT    = $PSScriptRoot
$IMG_DIR = "$ROOT\backend\data\images"
$DB_DIR  = "$ROOT\backend\db"

$IMG_DIR_CYG = $IMG_DIR -replace '\\', '/' -replace '^C:', '/cygdrive/c'
$DB_DIR_CYG  = $DB_DIR  -replace '\\', '/' -replace '^C:', '/cygdrive/c'
$EC2_KEY_FWD = $EC2_KEY -replace '\\', '/'
$SSH = "C:/Windows/System32/OpenSSH/ssh.exe"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " EC2 Sync 시작" -ForegroundColor Cyan
Write-Host "========================================="

Write-Host "[이미지] 새 파일만 전송 중..."
rsync -avz --ignore-existing -e "$SSH -i '$EC2_KEY_FWD' -o StrictHostKeyChecking=no" "$IMG_DIR_CYG/" "${EC2_HOST}:${EC2_IMG_DIR}/"

Write-Host ""
Write-Host "[DB JSON] 동기화 중..."
rsync -avz -e "$SSH -i '$EC2_KEY_FWD' -o StrictHostKeyChecking=no" "$DB_DIR_CYG/" "${EC2_HOST}:${EC2_DB_DIR}/" --include="*.json" --exclude="*"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " 완료!" -ForegroundColor Green
Write-Host "========================================="
