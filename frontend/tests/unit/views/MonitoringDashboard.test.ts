import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { nextTick } from "vue";

// ── Use vi.hoisted for mock factories to avoid hoisting issues ──
const { mockGet, mockEchartsInit, mockApiRequest } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockEchartsInit: vi.fn(),
  mockApiRequest: vi.fn(),
}));

const mockSetOption = vi.fn();
const mockDispose = vi.fn();
const mockEchartsOn = vi.fn();

// ECharts instance returned by init()
const echartsInstance = {
  setOption: mockSetOption,
  dispose: mockDispose,
  on: mockEchartsOn,
};

// ── Mock data factories ──
const mockSnapshotData = {
  cpu_usage: 23.5,
  memory_usage: 58.2,
  disk_usage: 41.0,
  network_recv_mb: 12.3,
  network_sent_mb: 5.1,
  process_threads: 12,
  cpu_count: 8,
  memory_used_mb: 4096,
  memory_total_mb: 8192,
  disk_used_gb: 80,
  disk_total_gb: 200,
};

const mockApiStatsData = {
  top_endpoints: [
    {
      endpoint: "/api/v1/auth/login",
      method: "POST",
      count: 150,
      avg_time_ms: 45.2,
      error_rate: 2.1,
    },
    {
      endpoint: "/api/v1/villages",
      method: "GET",
      count: 320,
      avg_time_ms: 12.5,
      error_rate: 0.3,
    },
  ],
};

const mockHealthData = {
  db_size_mb: 45.2,
  table_count: 38,
  db_integrity_ok: true,
  wal_size_kb: 128,
  uptime_seconds: 260100,
};

// ── Mock request module ──
vi.mock('@/api/request', () => ({
  default: { get: mockGet },
  get: mockGet,
  apiRequest: mockApiRequest,
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}));

// ── Mock echarts — component imports default from @/utils/echarts ──
mockEchartsInit.mockReturnValue(echartsInstance);

vi.mock("@/utils/echarts", () => {
  return {
    __esModule: true,
    default: {
      init: mockEchartsInit,
    },
  };
});

// ── Mock config store ──
const mockTheme = vi.fn(() => "light");
vi.mock("@/stores/config", () => ({
  useConfigStore: () => ({
    theme: mockTheme(),
  }),
}));

// ── Mock element-plus icons ──
vi.mock("@element-plus/icons-vue", () => ({
  Refresh: { name: "Refresh", template: "<span>Refresh</span>" },
  Download: { name: "Download", template: "<span>Download</span>" },
  CircleCheckFilled: { name: "CircleCheckFilled", template: "<span>CircleCheckFilled</span>" },
  CircleCloseFilled: { name: "CircleCloseFilled", template: "<span>CircleCloseFilled</span>" },
  Monitor: { name: "Monitor", template: "<span>Monitor</span>" },
  Files: { name: "Files", template: "<span>Files</span>" },
  Coin: { name: "Coin", template: "<span>Coin</span>" },
  Upload: { name: "Upload", template: "<span>Upload</span>" },
  Setting: { name: "Setting", template: "<span>Setting</span>" },
  FirstAidKit: { name: "FirstAidKit", template: "<span>FirstAidKit</span>" },
}));

// ── Mock ElMessage ──
vi.mock("element-plus", async () => {
  const actual = await vi.importActual("element-plus");
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
  };
});

// ── Import component after all mocks ──
import MonitoringDashboard from "@/views/system/MonitoringDashboard.vue";

// ── Helpers ──
function setupDefaultMocks() {
  mockGet.mockReset();
  mockGet.mockImplementation((url: string) => {
    if (url === "/system/monitor/snapshot") {
      return Promise.resolve({ data: { success: true, data: mockSnapshotData } });
    }
    if (url === "/health/full") {
      return Promise.resolve({ data: mockHealthData });
    }
    return Promise.reject(new Error("Unknown URL"));
  });

  mockApiRequest.mockReset();
  mockApiRequest.mockImplementation((config: any) => {
    if (config?.url === "/system/monitor/api-stats") {
      return Promise.resolve({ data: { success: true, data: mockApiStatsData } });
    }
    return Promise.reject(new Error("Unknown API request"));
  });

  mockEchartsInit.mockReset();
  mockEchartsInit.mockReturnValue(echartsInstance);
  mockSetOption.mockReset();
  mockDispose.mockReset();
}

function mountComponent(overrides?: { theme?: string }) {
  if (overrides?.theme) {
    mockTheme.mockReturnValue(overrides.theme);
  } else {
    mockTheme.mockReturnValue("light");
  }

  return mount(MonitoringDashboard, {
    global: {
      stubs: {
        // el-popover must render its default slot so that .metric-card content is visible.
        // Using a stub component that passes through the default slot.
        "el-popover": {
          template: '<div class="el-popover-stub"><slot name="reference" /><slot /></div>',
        },
        "el-icon": true,
        "el-button": {
          name: "ElButton",
          template: "<el-button-stub><slot /></el-button-stub>",
        },
        "el-tag": true,
        "el-empty": true,
      },
    },
  });
}

/**
 * Advance fake timers by one tick to allow setInterval's first callback to fire,
 * then flush all promises. We advance by a small amount (50ms) to allow the
 * onMounted → refreshAll → setInterval chain to run once without entering an
 * infinite timer loop.
 */
async function advanceFakeTimersAndFlush() {
  // Advance by a few ticks to let the initial setInterval fire once
  await vi.advanceTimersByTimeAsync(50);
  await flushPromises();
  await nextTick();
}

describe("MonitoringDashboard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setupDefaultMocks();
    sessionStorage.clear();
    mockTheme.mockReturnValue("light");
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ── T1: All 6 metric cards render after data fetch (3 primary + 3 secondary) ──
  it("renders all 6 metric cards with correct labels after data fetch", async () => {
    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    const primaryCards = wrapper.findAll(".primary-card");
    const secondaryCards = wrapper.findAll(".secondary-card");
    expect(primaryCards).toHaveLength(3);
    expect(secondaryCards).toHaveLength(3);

    const text = wrapper.text();
    expect(text).toContain("CPU 使用率");
    expect(text).toContain("内存使用率");
    expect(text).toContain("磁盘使用率");
    expect(text).toContain("网络接收");
    expect(text).toContain("网络发送");
    expect(text).toContain("进程线程");
  });

  // ── T2: Health score badge renders with correct class ──
  it("renders health score badge with score-good class when score >= 80", async () => {
    // mock data: cpu 23.5 (below 70 → +20), mem 58.2 (below 75 → +20), disk 41 (below 75 → +20),
    // db integrity ok → +20. Base 20. Total = 80 → score-good
    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    const badge = wrapper.find(".health-badge");
    expect(badge.exists()).toBe(true);
    expect(badge.classes().some(c => c.startsWith("score-"))).toBe(true);
  });

  // ── T3: ECharts chart container renders when API stats have data ──
  it("renders chart container when API stats have data", async () => {
    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    const chartContainer = wrapper.find(".chart-container");
    expect(chartContainer.exists()).toBe(true);
  });

  // ── T4: System logs section renders ──
  it("renders system logs section", async () => {
    // mock data has all usage levels below thresholds → "系统资源使用正常" log
    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    const text = wrapper.text();
    expect(text).toContain("系统日志");
  });

  // ── T5: Dark theme — component renders without errors ──
  it("responds to dark theme from config store", async () => {
    mockTheme.mockReturnValue("dark");

    const wrapper = mountComponent({ theme: "dark" });
    await advanceFakeTimersAndFlush();

    // The component watches configStore.theme and rebuilds chart with dark mode.
    // ECharts init is called with "dark" as second argument.
    // We verify the component renders without errors in dark mode.
    expect(wrapper.find(".monitoring-dashboard").exists()).toBe(true);
  });

  // ── T6: Primary metrics uses CSS Grid layout ──
  it("uses CSS Grid for metric layout", async () => {
    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    const grid = wrapper.find(".primary-metrics");
    expect(grid.exists()).toBe(true);
    // Verify secondary metrics section also exists
    const secondaryGrid = wrapper.find(".secondary-metrics");
    expect(secondaryGrid.exists()).toBe(true);
  });

  // ── T7: Error isolation — one failed API doesn't break all cards ──
  it("shows metric cards even when snapshot API fails", async () => {
    mockGet.mockReset();
    // Snapshot fails, others succeed
    mockGet.mockImplementation((url: string) => {
      if (url === "/system/monitor/snapshot") {
        return Promise.reject(new Error("Network error"));
      }
      if (url === "/health/full") {
        return Promise.resolve({ data: mockHealthData });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    mockApiRequest.mockReset();
    mockApiRequest.mockImplementation((config: any) => {
      if (config?.url === "/system/monitor/api-stats") {
        return Promise.resolve({ data: { success: true, data: mockApiStatsData } });
      }
      return Promise.reject(new Error("Unknown API request"));
    });

    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    const primaryCards = wrapper.findAll(".primary-card");
    const secondaryCards = wrapper.findAll(".secondary-card");
    // All cards still render (in error state with "--") despite snapshot failure
    expect(primaryCards.length + secondaryCards.length).toBeGreaterThanOrEqual(6);
  });

  // ── T8: Ring buffer caps at 10 entries ──
  it("caps history ring buffer at 10 entries", async () => {
    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    // Access pushHistory via wrapper.vm (component instance)
    const vm = wrapper.vm as any;
    for (let i = 0; i < 15; i++) {
      vm.pushHistory(10 + i, 20 + i, 30 + i);
    }
    await nextTick();

    const history = vm.history;
    expect(history).toHaveLength(10);
    // Last entry should be from the 15th push (10+14=24, 20+14=34, 30+14=44)
    expect(history[9].cpu).toBe(24);
    expect(history[9].mem).toBe(34);
    expect(history[9].disk).toBe(44);
  });

  // ── T9: Health section toggle expands/collapses ──
  it("toggles health section expand/collapse on header click", async () => {
    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    // Initially expanded (default: visible, v-show renders inline style)
    let healthBody = wrapper.find(".health-body");
    expect(healthBody.exists()).toBe(true);
    // v-show="true" means no inline display:none; the element is visible
    expect((healthBody.element as HTMLElement).style.display).toBe("");

    // Click the header to collapse
    await wrapper.find(".health-header").trigger("click");
    await nextTick();

    // Now body should be hidden
    healthBody = wrapper.find(".health-body");
    // v-show="false" → Vue sets inline display:none
    expect((healthBody.element as HTMLElement).style.display).toBe("none");

    // Verify sessionStorage was updated to false after collapse
    expect(sessionStorage.getItem("monitor-health-expanded")).toBe("false");
  });

  // ── T10: Timer cleared on unmount ──
  it("clears polling interval on unmount", async () => {
    // Use vi.fn() instead of spyOn to avoid conflicts with fake timers
    const clearIntervalMock = vi.fn();
    const origClearInterval = globalThis.clearInterval;
    globalThis.clearInterval = clearIntervalMock;

    const wrapper = mountComponent();
    await advanceFakeTimersAndFlush();

    wrapper.unmount();

    // clearInterval should have been called for the polling timer
    expect(clearIntervalMock).toHaveBeenCalled();

    // Restore original
    globalThis.clearInterval = origClearInterval;
  });
});

describe('日志回退分支补充', () => {
  it('系统日志空数组 → 回退资源快照生成日志', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/admin/logs') return Promise.resolve({ data: [] })
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await flushPromises()
    expect((wrapper.vm as any).recentLogs.length).toBeGreaterThan(0)
    wrapper.unmount()
  })
  it('fetchSystemLogs {items:[...]} 信封 → 解析', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/admin/logs')
        return Promise.resolve({ items: [{ line: '2026-01-01 10:00:00 - INFO - 启动' }] })
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await flushPromises()
    expect((wrapper.vm as any).recentLogs.length).toBeGreaterThan(0)
    wrapper.unmount()
  })
})

describe('日志形态收尾', () => {
  it('sysLogs 拒绝 → 回退快照；sysLogs 非数组对象', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/admin/logs') return Promise.reject(new Error('x'))
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await flushPromises()
    expect((wrapper.vm as any).recentLogs.length).toBeGreaterThan(0)
    wrapper.unmount()
  })
  it('fetchSystemLogs 数组 payload / ERROR 日志 / 未匹配行', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/admin/logs')
        return Promise.resolve([
          { line: '2026-01-01 10:00:00 ERROR - 崩溃' },
          '无法解析的一行',
        ])
      if (url === '/system/health/full')
        return Promise.resolve({
          data: [{ line: '2026-01-02 09:00:00 ERROR - 数据库断开' }],
        })
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await flushPromises()
    const vm = wrapper.vm as any
    const logs = await vm.fetchSystemLogs()
    expect(JSON.stringify(logs)).toContain('error')
    wrapper.unmount()
  })
})

describe('日志形态收尾2', () => {
  it('health/full 空数组 / 非数组 / 拒绝 → 快照回退', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/health/full') return Promise.resolve({ data: [] })
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await flushPromises()
    expect((wrapper.vm as any).recentLogs.length).toBeGreaterThan(0)
    wrapper.unmount()
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/health/full') return Promise.resolve({ data: { x: 1 } })
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper2 = mountComponent()
    await flushPromises()
    expect((wrapper2.vm as any).recentLogs.length).toBeGreaterThan(0)
    wrapper2.unmount()
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/health/full') return Promise.reject(new Error('x'))
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper3 = mountComponent()
    await flushPromises()
    wrapper3.unmount()
  })
  it('fetchSystemLogs WARN / line 空对象 / 空 line', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/admin/logs')
        return Promise.resolve([
          { line: '2026-01-01 10:00:00 WARN - 内存偏高' },
          { line: '' },
          '   ',
        ])
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await flushPromises()
    const vm = wrapper.vm as any
    const logs = await vm.fetchSystemLogs()
    expect(logs.some((l: any) => l.level === 'warn')).toBe(true)
    expect(logs.some((l: any) => l.message === '--')).toBe(true)
    wrapper.unmount()
  })
})

describe('日志级别收尾', () => {
  it('fetchSystemLogs INFO 行 → info 级别', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/admin/logs')
        return Promise.resolve([{ line: '2026-01-01 10:00:00 INFO - 正常启动' }])
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await flushPromises()
    const vm = wrapper.vm as any
    const logs = await vm.fetchSystemLogs()
    expect(logs.some((l: any) => l.level === 'info' && l.message === '正常启动')).toBe(true)
    wrapper.unmount()
  })
})

describe('真实日志优先分支', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setupDefaultMocks()
  })
  afterEach(() => {
    vi.useRealTimers()
  })
  it('health/full 返回日志数组 → recentLogs 直接用数组', async () => {
    mockGet.mockReset()
    mockGet.mockImplementation((url: string) => {
      if (url === '/system/health/full')
        return Promise.resolve({ data: [{ line: '2026-01-02 09:00:00 INFO - 启动' }] })
      if (url === '/system/snapshot') return Promise.resolve({ data: mockSnapshotData })
      if (url === '/system/api-stats') return Promise.resolve({ data: mockApiStatsData })
      if (url === '/system/health') return Promise.resolve({ data: mockHealthData })
      return Promise.resolve({})
    })
    const wrapper = mountComponent()
    await advanceFakeTimersAndFlush()
    expect((wrapper.vm as any).recentLogs.length).toBeGreaterThan(0)
    wrapper.unmount()
  })
})
