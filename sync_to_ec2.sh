#!/bin/bash
# 크롤링 후 EC2로 새 파일만 전송 (브랜드 + 인스타 전체)
# 사용법: bash sync_to_ec2.sh

EC2_HOST="ubuntu@107.22.8.250"
EC2_KEY="C:/Users/User/Desktop/CRAI/ku-hys-01-key.pem"
EC2_IMG_DIR="/home/ubuntu/CRAI/backend/data/images"
EC2_DB_DIR="/home/ubuntu/CRAI/backend/db"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_IMG_DIR="$SCRIPT_DIR/backend/data/images"
LOCAL_DB_DIR="$SCRIPT_DIR/backend/db"

echo "========================================="
echo " CRAI EC2 Sync 시작"
echo "========================================="

echo ""
echo "[1/2] 이미지 전송 중... (기존 파일 스킵)"
rsync -avz --ignore-existing \
    -e "ssh -i '$EC2_KEY' -o StrictHostKeyChecking=no" \
    "$LOCAL_IMG_DIR/" \
    "$EC2_HOST:$EC2_IMG_DIR/"

echo ""
echo "[2/2] DB JSON 동기화 중..."
rsync -avz \
    -e "ssh -i '$EC2_KEY' -o StrictHostKeyChecking=no" \
    "$LOCAL_DB_DIR/"*.json \
    "$EC2_HOST:$EC2_DB_DIR/"

echo ""
echo "========================================="
echo " 완료!"
echo "========================================="
