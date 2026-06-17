"""
EC2로 새 파일만 전송
사용법: python sync_to_ec2.py
"""
import subprocess
from pathlib import Path

KEY       = r"C:\Users\User\Desktop\CRAI\ku-hys-01-key.pem"
HOST      = "ubuntu@107.22.8.250"
LOCAL_IMG = Path(r"C:\Users\User\Desktop\CRAI\backend\data\images")
LOCAL_DB  = Path(r"C:\Users\User\Desktop\CRAI\backend\db")
EC2_IMG   = "/home/ubuntu/CRAI/backend/data/images"
EC2_DB    = "/home/ubuntu/CRAI/backend/db"

SSH = r"C:\Windows\System32\OpenSSH\ssh.exe"
SCP = r"C:\Windows\System32\OpenSSH\scp.exe"
SSH_OPTS = ["-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10"]

SKIP_BRANDS = {"generated"}


def ssh_run(cmd: str) -> str:
    result = subprocess.run(
        [SSH] + SSH_OPTS + [HOST, cmd],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()


print("=========================================")
print(" EC2 Sync 시작")
print("=========================================\n")

# EC2 파일 목록 + 디렉토리 생성 한 번에
print("[1/2] EC2 상태 확인 및 디렉토리 준비 중...")
brands = [d.name for d in sorted(LOCAL_IMG.iterdir()) if d.is_dir() and d.name not in SKIP_BRANDS]
mkdir_cmd = " && ".join([f"mkdir -p {EC2_IMG}/{b}" for b in brands] + [f"mkdir -p {EC2_DB}"])
ssh_run(mkdir_cmd)

ec2_files_raw = ssh_run(f"find {EC2_IMG} -type f -name '*.jpg' 2>/dev/null")
ec2_files = set(Path(f).name for f in ec2_files_raw.splitlines() if f)
print(f"  EC2 보유 이미지: {len(ec2_files)}개\n")

# 이미지 전송
print("[2/2] 이미지 전송 중...")
total_new = 0
total_skip = 0

for brand in brands:
    brand_dir = LOCAL_IMG / brand
    images = list(brand_dir.glob("*.jpg"))
    new_files = [f for f in images if f.name not in ec2_files]
    skip = len(images) - len(new_files)
    total_skip += skip

    print(f"  [{brand}] 전체 {len(images)}개 | 전송 {len(new_files)}개 | 스킵 {skip}개")

    if not new_files:
        continue

    # 브랜드별로 한 번에 scp
    subprocess.run(
        [SCP] + SSH_OPTS + [str(f) for f in new_files] + [f"{HOST}:{EC2_IMG}/{brand}/"],
        check=False
    )
    total_new += len(new_files)

print(f"\n[이미지 완료] 전송 {total_new}개 / 스킵 {total_skip}개")

# JSON 전송
print("\n[DB JSON] 동기화 중...")
json_files = list(LOCAL_DB.glob("*.json"))
if json_files:
    subprocess.run(
        [SCP] + SSH_OPTS + [str(f) for f in json_files] + [f"{HOST}:{EC2_DB}/"],
        check=False
    )
    for f in json_files:
        print(f"  전송: {f.name}")

print("\n=========================================")
print(" 완료!")
print("=========================================")
