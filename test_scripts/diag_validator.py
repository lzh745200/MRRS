import sys
sys.path.insert(0, 'backend')
from app.services.package_record_validator import validate_records
# 样本1：数字字符串
r1 = validate_records("villages", [{"village_name": "测试村X", "population": "999"}])
print("sample1 (population str):", {k: len(v) for k, v in r1.items()})
for c in r1.get("corrected", []):
    print("  corrected:", c)
for c in r1.get("rejected", []):
    print("  rejected:", c)
# 样本2：必填缺失
r2 = validate_records("villages", [{"population": 100}])
print("sample2 (no name):", {k: len(v) for k, v in r2.items()})
for c in r2.get("rejected", []):
    print("  rejected:", c)
# 样本3：电话分隔符
r3 = validate_records("schools", [{"name": "校A", "contact_phone": "0851-1234567"}])
print("sample3 (phone):", {k: len(v) for k, v in r3.items()})
for c in r3.get("corrected", []):
    print("  corrected:", c)
