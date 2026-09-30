import json
import unittest

from fastapi import BackgroundTasks

from app.api.v1.system import tasks as tasks_mod


def test_probe(client_with_mocked_auth):
    cap = {}

    def _c(self_, fn, *args, **kwargs):
        cap["fn"] = fn
        cap["args"] = args

    with unittest.mock.patch.object(tasks_mod, "_tasks", {}), unittest.mock.patch.object(
        BackgroundTasks, "add_task", _c
    ):
        r = client_with_mocked_auth.post(
            "/api/v1/system/tasks", json={"task_type": "demo", "task_name": "d"}
        )
    tid = json.loads(r.content)["data"]["task_id"]

    trace = []
    live = {tid: {"status": "pending", "progress": 0.0}}
    calls = {"n": 0}

    def _sleep(*_a, **_k):
        calls["n"] += 1
        trace.append("sleep%d" % calls["n"])
        if calls["n"] >= 5:
            live.pop(tid, None)
            trace.append("deleted")

    with unittest.mock.patch.object(tasks_mod, "_tasks", live), unittest.mock.patch(
        "time.sleep", _sleep
    ):
        cap["fn"](*cap["args"])

    # 观察收尾块的判空是否真的执行：若执行且 task 为 None，则 265 必然被计为覆盖
    print("TRACE", trace)
    print("FINAL", live)

    # 直接验证收尾块行为：构造一个"循环结束后才判空"的场景
    # （用 patch 掉 _tasks 的 get 打点，确认 262-265 是否到达）
    reached = {"writeback": False, "get": 0}
    live2 = {tid: {"status": "pending", "progress": 0.0}}
    orig_get = dict.get

    class _D(dict):
        def get(self, k, d=None):
            reached["get"] += 1
            return orig_get(self, k, d)

    d = _D(live2)
    with unittest.mock.patch.object(tasks_mod, "_tasks", d), unittest.mock.patch(
        "time.sleep", lambda *a, **k: None
    ):
        cap["fn"](*cap["args"])
    print("GET_CALLS", reached["get"], "RESULT", d)
