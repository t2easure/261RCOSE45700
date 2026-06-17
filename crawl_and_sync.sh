#!/bin/bash
# 브랜드 + 인스타 크롤링 후 EC2 자동 동기화
# 사용법: bash crawl_and_sync.sh

PYTHON="cmd /c python"
EC2_HOST="ubuntu@107.22.8.250"
EC2_KEY="C:/Users/User/Desktop/CRAI/ku-hys-01-key.pem"
EC2_IMG_DIR="/home/ubuntu/CRAI/backend/data/images"
EC2_DB_DIR="/home/ubuntu/CRAI/backend/db"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_IMG_DIR="$SCRIPT_DIR/backend/data/images"
LOCAL_DB_DIR="$SCRIPT_DIR/backend/db"

echo "========================================="
echo " [1/3] 브랜드 크롤링 시작"
echo "========================================="
$PYTHON "$SCRIPT_DIR/backend/crawlers/brand_scraper.py"
if [ $? -ne 0 ]; then
    echo "브랜드 크롤링 실패. 종료합니다."
    exit 1
fi

echo ""
echo "========================================="
echo " [2/3] 인스타그램 크롤링 시작"
echo "========================================="
$PYTHON "$SCRIPT_DIR/backend/crawlers/local_instagram_playwright.py"
if [ $? -ne 0 ]; then
    echo "인스타 크롤링 실패. 종료합니다."
    exit 1
fi

echo ""
echo "========================================="
echo " [3/3] EC2 동기화 시작"
echo "========================================="

echo ""
echo "[이미지] 새 파일만 전송 중..."
rsync -avz --ignore-existing \
    -e "ssh -i '$EC2_KEY' -o StrictHostKeyChecking=no" \
    "$LOCAL_IMG_DIR/" \
    "$EC2_HOST:$EC2_IMG_DIR/"

echo ""
echo "[DB JSON] 동기화 중..."
rsync -avz \
    -e "ssh -i '$EC2_KEY' -o StrictHostKeyChecking=no" \
    "$LOCAL_DB_DIR/"*.json \
    "$EC2_HOST:$EC2_DB_DIR/"

echo ""
echo "========================================="
echo " 전체 완료!"
echo "========================================="
