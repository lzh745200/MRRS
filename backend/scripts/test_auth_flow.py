#!/usr/bin/env python3
"""认证流程完整测试"""

import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1"
TEST_RESULTS = []

def log_test(name, success, details=""):
    """记录测试结果"""
    status = "[PASS]" if success else "[FAIL]"
    TEST_RESULTS.append((name, success, details))
    print(f"{status}: {name}")
    if details:
        print(f"   {details}")

def test_login():
    """测试登录接口"""
    print("\n" + "="*60)
    print("测试1: 用户登录")
    print("="*60)

    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": "admin", "password": "zgcZGC733035#"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200 and data.get("data"):
                access_token = data["data"].get("access_token")
                refresh_token = data.get("refresh_token")
                user = data["data"].get("user", {})

                log_test("登录接口", True, "获取到 access_token 和 refresh_token")
                log_test("用户角色", user.get("role") in ["admin", "super_admin"],
                        f"角色: {user.get('role')}")

                return access_token, refresh_token
            else:
                log_test("登录接口", False, f"响应格式错误: {data}")
                return None, None
        elif response.status_code == 401:
            log_test("登录接口", False, "密码错误或未授权")
            return None, None
        else:
            log_test("登录接口", False, f"状态码: {response.status_code}")
            return None, None

    except Exception as e:
        log_test("登录接口", False, f"异常: {e}")
        return None, None

def test_access_protected_api(access_token):
    """测试访问受保护API"""
    print("\n" + "="*60)
    print("测试2: 访问受保护API")
    print("="*60)

    headers = {"Authorization": f"Bearer {access_token}"}

    endpoints = [
        ("/auth/me", "获取当前用户信息"),
        ("/dashboard/stats", "仪表盘统计"),
        ("/projects?page=1&page_size=5", "项目列表"),
        ("/todos?page=1&page_size=50", "待办事项"),
    ]

    all_passed = True
    for endpoint, name in endpoints:
        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                log_test(f"{name}", True)
            elif response.status_code == 401:
                log_test(f"{name}", False, "401 Unauthorized - Token无效或过期")
                all_passed = False
            else:
                log_test(f"{name}", False, f"状态码: {response.status_code}")
                all_passed = False

        except Exception as e:
            log_test(f"{name}", False, f"异常: {e}")
            all_passed = False

    return all_passed

def test_token_refresh(refresh_token):
    """测试Token刷新"""
    print("\n" + "="*60)
    print("测试3: Token刷新")
    print("="*60)

    try:
        response = requests.post(
            f"{BASE_URL}/auth/refresh",
            json={"token": refresh_token},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200 and data.get("data"):
                new_access_token = data["data"].get("access_token")
                new_refresh_token = data["data"].get("refresh_token")

                log_test("Token刷新", True, "成功获取新token")
                return new_access_token, new_refresh_token
            else:
                log_test("Token刷新", False, f"响应格式错误: {data}")
                return None, None
        elif response.status_code == 401:
            log_test("Token刷新", False, "401 - Refresh Token无效或已过期")
            return None, None
        else:
            log_test("Token刷新", False, f"状态码: {response.status_code}")
            return None, None

    except Exception as e:
        log_test("Token刷新", False, f"异常: {e}")
        return None, None

def test_admin_apis(access_token):
    """测试管理员专属API"""
    print("\n" + "="*60)
    print("测试4: 管理员专属API")
    print("="*60)

    headers = {"Authorization": f"Bearer {access_token}"}

    endpoints = [
        ("/system/config", "系统配置"),
        ("/system/audit", "操作审计"),
        ("/users", "用户列表"),
    ]

    for endpoint, name in endpoints:
        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                log_test(f"{name}", True)
            elif response.status_code == 401:
                log_test(f"{name}", False, "401 Unauthorized")
            elif response.status_code == 403:
                log_test(f"{name}", False, "403 Forbidden - 无权限")
            else:
                log_test(f"{name}", False, f"状态码: {response.status_code}")

        except Exception as e:
            log_test(f"{name}", False, f"异常: {e}")

def test_reused_refresh_token(refresh_token):
    """测试刷新token重用（应该失败）"""
    print("\n" + "="*60)
    print("测试5: Refresh Token重用检测")
    print("="*60)

    try:
        # 第一次刷新
        response1 = requests.post(
            f"{BASE_URL}/auth/refresh",
            json={"token": refresh_token},
            timeout=10
        )

        if response1.status_code == 200:
            # 第二次使用同一个refresh token（应该失败）
            response2 = requests.post(
                f"{BASE_URL}/auth/refresh",
                json={"token": refresh_token},
                timeout=10
            )

            if response2.status_code == 401:
                log_test("Token重用检测", True, "旧token已被正确吊销")
                return True
            else:
                log_test("Token重用检测", False, f"旧token仍可用，状态码: {response2.status_code}")
                return False
        else:
            log_test("Token重用检测", False, f"第一次刷新失败: {response1.status_code}")
            return False

    except Exception as e:
        log_test("Token重用检测", False, f"异常: {e}")
        return False

def print_summary():
    """打印测试摘要"""
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)

    passed = sum(1 for _, success, _ in TEST_RESULTS if success)
    total = len(TEST_RESULTS)

    print(f"总计: {total} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {total - passed} 项")

    if passed == total:
        print("\n[OK] 所有测试通过！后端认证系统工作正常。")
        print("\n如果前端仍然遇到401错误，问题可能在于:")
        print("1. 前端存储了旧的token")
        print("2. 前端没有正确携带Authorization头")
        print("3. 浏览器缓存问题")
        print("\n建议: 清除浏览器存储后重新登录")
    else:
        print("\n[ERROR] 部分测试失败，请检查后端日志")

    return passed == total

def main():
    print("="*60)
    print("认证流程完整测试")
    print("="*60)
    print(f"测试地址: {BASE_URL}")

    # 测试1: 登录
    access_token, refresh_token = test_login()

    if not access_token or not refresh_token:
        print("\n[ERROR] 登录失败，无法继续测试")
        return 1

    # 测试2: 访问受保护API
    test_access_protected_api(access_token)

    # 测试3: Token刷新
    new_access, new_refresh = test_token_refresh(refresh_token)

    if new_access:
        # 使用新token测试管理员API
        test_admin_apis(new_access)

        # 测试4: 测试token重用检测
        test_reused_refresh_token(new_refresh)

    # 打印摘要
    success = print_summary()

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
