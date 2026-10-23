#!/usr/bin/env python
"""Deep import test - verify all modules can be imported."""
import os
import sys
import importlib
import traceback

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-ci"

# Test 1: Main app import
print("=" * 60)
print("Test 1: Main app import")
print("=" * 60)
try:
    from app.main import app
    print(f"  PASS: app imported as {type(app).__name__}")
except Exception as e:
    print(f"  FAIL: {e}")
    traceback.print_exc()
    sys.exit(1)

# Test 2: All API v1 business modules
print("\nTest 2: All API v1 business modules")
print("=" * 60)
business_modules = [
    'organization', 'policy', 'projects', 'school',
    'supported_village', 'supported_village_export',
    'rural_works',
    'villages', 'village_templates', 'validation', 'report_templates',
    'approval', 'messages', 'feedback', 'todos', 'ai', 'map',
    'project_milestones', 'funds', 'fund_budgets', 'fund_lifecycle',
    'work_logs', 'assessment', 'system_health', 'performance',
    'monitoring_legacy', 'data_quality', 'ai_enhanced', 'data_sync',
    'offline_map', 'batch_operations', 'sync', 'user_permissions',
    'machine_code', 'effectiveness', 'sentiment', 'messages_extended',
    'encryption', 'search', 'menus', 'permission_package',
]
failed = []
for mod_name in business_modules:
    try:
        mod = importlib.import_module(f'app.api.v1.{mod_name}')
        if not hasattr(mod, 'router'):
            print(f"  WARN: {mod_name} has no 'router' attribute")
            failed.append(f"{mod_name} (no router)")
    except Exception as e:
        print(f"  FAIL: {mod_name}: {e}")
        failed.append(f"{mod_name} ({e})")

if failed:
    print(f"\n  {len(failed)} module(s) failed: {failed}")
else:
    print(f"  All {len(business_modules)} business modules imported successfully")

# Test 3: All models
print("\nTest 3: All models import")
print("=" * 60)
import pkgutil
import app.models as models_pkg
model_errors = []
for importer, modname, ispkg in pkgutil.iter_modules(models_pkg.__path__):
    try:
        importlib.import_module(f'app.models.{modname}')
    except Exception as e:
        print(f"  FAIL: app.models.{modname}: {e}")
        model_errors.append(modname)

if not model_errors:
    print(f"  All models imported successfully")
else:
    print(f"  {len(model_errors)} model(s) failed: {model_errors}")

# Test 4: All schemas
print("\nTest 4: All schemas import")
print("=" * 60)
import app.schemas as schemas_pkg
schema_errors = []
for importer, modname, ispkg in pkgutil.iter_modules(schemas_pkg.__path__):
    try:
        importlib.import_module(f'app.schemas.{modname}')
    except Exception as e:
        print(f"  FAIL: app.schemas.{modname}: {e}")
        schema_errors.append(modname)

if not schema_errors:
    print(f"  All schemas imported successfully")
else:
    print(f"  {len(schema_errors)} schema(s) failed: {schema_errors}")

# Test 5: All services
print("\nTest 5: All services import")
print("=" * 60)
import app.services as services_pkg
service_errors = []
for importer, modname, ispkg in pkgutil.iter_modules(services_pkg.__path__):
    try:
        importlib.import_module(f'app.services.{modname}')
    except Exception as e:
        print(f"  FAIL: app.services.{modname}: {e}")
        service_errors.append(modname)

if not service_errors:
    print(f"  All services imported successfully")
else:
    print(f"  {len(service_errors)} service(s) failed: {service_errors}")

# Test 6: Security utilities
print("\nTest 6: Security utilities")
print("=" * 60)
try:
    from app.core.security import (
        hash_password, verify_password, create_access_token,
        create_refresh_token, decode_token, get_current_user
    )
    print("  PASS: All security functions available")
except ImportError as e:
    print(f"  FAIL: {e}")

# Test 7: Middleware
print("\nTest 7: Middleware import")
print("=" * 60)
middleware_list = [
    'app.middleware.body_size_limit',
    'app.middleware.camel_to_snake',
    'app.middleware.csrf_middleware',
    'app.middleware.metrics_middleware',
    'app.middleware.request_id',
    'app.middleware.request_logger',
]
for mw in middleware_list:
    try:
        importlib.import_module(mw)
        print(f"  PASS: {mw}")
    except Exception as e:
        print(f"  FAIL: {mw}: {e}")

print("\n" + "=" * 60)
print("Deep import test complete.")
print("=" * 60)
