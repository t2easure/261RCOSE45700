# 브랜드 + 인스타 크롤링 후 EC2 자동 동기화
# 사용법: powershell -ExecutionPolicy Bypass -File crawl_and_sync.ps1

$ROOT = $PSScriptRoot

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " [1/3] 브랜드 크롤링 시작" -ForegroundColor Cyan
Write-Host "========================================="
$env:HEADLESS = "false"
python "$ROOT\backend\crawlers\brand_scraper.py"
$env:HEADLESS = ""
if ($LASTEXITCODE -ne 0) { Write-Host "브랜드 크롤링 실패. 종료합니다." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " [2/3] 인스타그램 크롤링 시작" -ForegroundColor Cyan
Write-Host "========================================="
python "$ROOT\backend\crawlers\local_instagram_playwright.py"
if ($LASTEXITCODE -ne 0) { Write-Host "인스타 크롤링 실패. 종료합니다." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " [3/3] EC2 동기화 시작" -ForegroundColor Cyan
Write-Host "========================================="
python "$ROOT\sync_to_ec2.py"

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " 전체 완료!" -ForegroundColor Green
Write-Host "========================================="
