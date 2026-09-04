"""Cross-platform pre-commit hooks (replaces bash-only hooks)."""
import subprocess, sys

def run(args, **kwargs):
    result = subprocess.run(args, **kwargs)
    sys.exit(result.returncode)

if __name__ == "__main__":
    hook = sys.argv[1]
    python = sys.executable

    if hook == "check_dockerfile_tail":
        import pathlib, re
        failed = [
            str(f) for f in pathlib.Path(".").glob("docker/Dockerfile*")
            if re.search(r"RUN .* 2>&1$", f.read_text(encoding="utf-8"), re.MULTILINE)
        ]
        if failed:
            for f in failed:
                print(f"ERROR: {f} has RUN commands without | tail")
                print("(under QEMU, truncation is intentional)")
            sys.exit(1)
        sys.exit(0)

    elif hook == "flake8":
        # 与 CI 的 lint 任务同一判据（--max-complexity=16）；显式传参避免
        # 配置发现结果随 cwd 漂移导致本地与 CI 判据不一致
        run([python, "-m", "flake8",
             "--max-line-length=120", "--count", "--max-complexity=16",
             "backend/app/"])

    elif hook == "bandit":
        # 与 CI 同一判据 -ll（中危及以上）。不带 -ll 时 backend/app 下 42 个
        # 低危发现会让钩子恒失败，而 CI 根本不拦这些 —— 判据不一致的后果是
        # 没人愿意装钩子，整个 stage-2 门禁形同虚设。
        # -ll 通过即代表中危/高危为零；低危仅作信息，不作阻断。
        run([python, "-m", "bandit", "-r", "backend/app/", "-ll"])

    elif hook == "vue_tsc":
        run("npx vue-tsc --noEmit", cwd="frontend", shell=True)

    else:
        print(f"Unknown hook: {hook}")
        sys.exit(1)
