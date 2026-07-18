import os

print("=== BƯỚC 1: Kiểm tra file .env có tồn tại không ===")
env_path = os.path.join(os.path.dirname(os.path.abspath("config.py")), ".env")
print("Đường dẫn .env kỳ vọng:", os.path.join(os.getcwd(), ".env"))
print("File .env tồn tại:", os.path.exists(".env"))
print()

print("=== BƯỚC 2: import config (kích hoạt load_dotenv) ===")
import config
print("USE_BEDROCK   :", config.USE_BEDROCK)
print("BEDROCK_MODEL_ID:", config.BEDROCK_MODEL_ID)
print("BEDROCK_REGION  :", config.BEDROCK_REGION)
print()

print("=== BƯỚC 3: Kiểm tra os.environ SAU KHI import config ===")
key = os.environ.get("AWS_ACCESS_KEY_ID", "")
secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
token = os.environ.get("AWS_SESSION_TOKEN", "")
print(f"AWS_ACCESS_KEY_ID     : [{key[:6]}...] (độ dài: {len(key)})" if key else "AWS_ACCESS_KEY_ID     : RỖNG")
print(f"AWS_SECRET_ACCESS_KEY : {'có, độ dài ' + str(len(secret)) if secret else 'RỖNG'}")
print(f"AWS_SESSION_TOKEN     : {'có, độ dài ' + str(len(token)) if token else 'RỖNG (chỉ cần nếu key bắt đầu bằng ASIA)'}")
print()

print("=== BƯỚC 4: boto3 có nhận được credentials không ===")
import boto3
creds = boto3.Session().get_credentials()
if creds is None:
    print("=> KHÔNG CÓ credentials nào cả (None)")
else:
    frozen = creds.get_frozen_credentials()
    print(f"=> CÓ credentials: access_key bắt đầu bằng '{frozen.access_key[:4]}...'")
    print(f"   method nguồn credentials: {creds.method}")
