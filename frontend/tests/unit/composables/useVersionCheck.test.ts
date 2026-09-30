import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('element-plus', () => ({
  ElMessage: { warning: vi.fn() },
}));

import { ElMessage } from 'element-plus';
import { checkVersion, getRunningVersion } from '@/composables/useVersionCheck';

/** 统一的 window.location 桩：replace/reload 都必须是函数（否则 1500ms 后回调抛 TypeError） */
function stubLocation(extra: Record<string, unknown> = {}) {
  const replace = vi.fn();
  const reload = vi.fn();
  Object.defineProperty(window, 'location', {
    value: { href: 'http://localhost/dashboard', replace, reload, ...extra },
    writable: true,
  });
  return { replace, reload };
}

function mockVersion(version: unknown) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(version === undefined ? {} : { version }),
  });
}

describe('useVersionCheck/checkVersion', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
    vi.useFakeTimers();
    stubLocation();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('version matches → does not reload', async () => {
    localStorage.setItem('app_version', '1.3.0');
    mockVersion('1.3.0');
    const { replace, reload } = stubLocation();
    await checkVersion();
    expect(reload).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it('version mismatch → does not throw', async () => {
    localStorage.setItem('app_version', '1.2.0');
    mockVersion('1.3.0');
    await expect(checkVersion()).resolves.toBeUndefined();
    await vi.advanceTimersByTimeAsync(2000);
  });

  it('fetch failure (404) → silent skip, no exception', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network error'));
    await expect(checkVersion()).resolves.toBeUndefined();
  });

  it('first visit (no cached version) → saves version, no reload', async () => {
    mockVersion('1.3.0');
    await checkVersion();
    expect(localStorage.getItem('app_version')).toBe('1.3.0');
  });

  it('HTTP error (ok=false) → silent skip, no write', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    await expect(checkVersion()).resolves.toBeUndefined();
    expect(localStorage.getItem('app_version')).toBeNull();
  });

  it('missing version field → silent skip', async () => {
    mockVersion(undefined);
    await expect(checkVersion()).resolves.toBeUndefined();
    expect(localStorage.getItem('app_version')).toBeNull();
  });

  // 2026-09-30 深审修复：原先"先写 app_version=1.3.0 再延迟刷新"——一旦刷新被拦/
  // 缓存未破，下次比对即相等 → 永久停留在旧代码且再无检测机会。现改为：
  // 仅在"运行包版本 === 服务端版本"时落缓存；检测到新版本时只落一次性护栏并破缓存跳转。
  it('version mismatch → warns and 破缓存 replace after delay（不提前写缓存）', async () => {
    localStorage.setItem('app_version', '1.2.0');
    mockVersion('1.3.0');
    const { replace } = stubLocation({ href: 'http://localhost/funds/analysis?y=1#top' });

    await checkVersion();
    // 未写缓存：刷新成功（新包运行）后才由上面的"版本一致"分支落库
    expect(localStorage.getItem('app_version')).toBe('1.2.0');
    expect(sessionStorage.getItem('app_version_reload_for')).toBe('1.3.0');
    expect(ElMessage.warning).toHaveBeenCalledWith(
      expect.objectContaining({ message: '系统已更新至 v1.3.0，即将自动刷新...' })
    );
    expect(replace).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1500);
    expect(replace).toHaveBeenCalledTimes(1);
    // 带版本参数破缓存，而非 location.reload() 命中入口 HTML 缓存
    expect(replace).toHaveBeenCalledWith('/funds/analysis?y=1&_v=1.3.0#top');
  });

  it('已为该版本刷新过一次仍不一致 → 只提示人工刷新，不再自动刷新（防死循环）', async () => {
    localStorage.setItem('app_version', '1.2.0');
    sessionStorage.setItem('app_version_reload_for', '1.3.0');
    mockVersion('1.3.0');
    const { replace } = stubLocation();

    await checkVersion();
    await vi.advanceTimersByTimeAsync(5000);

    expect(replace).not.toHaveBeenCalled();
    expect(ElMessage.warning).toHaveBeenCalledWith(
      expect.objectContaining({
        message: '系统已更新至 v1.3.0，自动刷新未生效，请手动刷新页面',
      })
    );
  });

  it('运行包版本 === 服务端版本 → 落缓存并清护栏（刷新成功后的自愈路径）', async () => {
    const running = getRunningVersion();
    localStorage.setItem('app_version', '0.0.1');
    sessionStorage.setItem('app_version_reload_for', running);
    mockVersion(running);
    const { replace } = stubLocation();

    await checkVersion();
    await vi.advanceTimersByTimeAsync(2000);

    expect(localStorage.getItem('app_version')).toBe(running);
    expect(sessionStorage.getItem('app_version_reload_for')).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });

  it('破缓存 URL：href 为空 → 退回首页 + 版本参数', async () => {
    localStorage.setItem('app_version', '1.2.0');
    mockVersion('1.3.0');
    const { replace } = stubLocation({ href: '' });
    await checkVersion();
    await vi.advanceTimersByTimeAsync(1500);
    expect(replace).toHaveBeenCalledWith('/?_v=1.3.0');
  });

  it('破缓存 URL：href 畸形 → 退回首页 + 版本参数（不抛错）', async () => {
    localStorage.setItem('app_version', '1.2.0');
    mockVersion('1.3.0');
    const { replace } = stubLocation({ href: 'http://[' });
    await checkVersion();
    await vi.advanceTimersByTimeAsync(1500);
    expect(replace).toHaveBeenCalledWith('/?_v=1.3.0');
  });
});
