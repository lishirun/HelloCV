#!/usr/bin/env python3
"""一键验收脚本：按任务书的三条验收命令跑一遍，并逐行检查输出是否严格合法。

用法::

    python verify.py                 # 跑三条验收命令（第三条用本地假上游，不花钱）
    python verify.py --real-api      # 第三条改用真实 DeepSeek API（需要 DEEPSEEK_API_KEY）
    python verify.py --rounds 20     # 改对局轮数

三条命令对应任务书「3. 验收标准」的第 2 条：

    a) 离线兜底        run_gateway.py --offline
    b) 坏上游也不许崩   mock_llm_server.py + samples/requests.jsonl
    c) 完整对局        play_game.py --rounds 10

检查项（每条都打印 PASS/FAIL，最后给出总判定）：

* 每行输出都是合法 JSON，且**恰好** time + option 两个键；
* time 是非空字符串并且**与请求逐行对齐**（模型自报的 time 必须被丢弃）；
* option 只在 rock / scissor / paper 里；
* 一行进一行出：非空输入行数 == 输出行数，空行不算请求；
* 坏输入不转发给上游（不浪费钱）；
* 假上游在 reasoning_content 里写死 rock，只要输出不全是一个值，就说明没误用思维链；
* 鉴权头是 Bearer、开了 json_object、默认关思考模式；
* 空回复会触发重试（单独用 2 条预设坏回复验证）。

本脚本只做**外部校验**，不修改仓库里任何文件。退出码 0 = 全部通过。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认可能是 GBK，先把输出切到 UTF-8，避免中文/符号变乱码
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

SKELETON = Path(__file__).resolve().parent / "skeleton"
OPTIONS = ("rock", "scissor", "paper")
TIMEOUT = 180.0
MOCK_PORT = 8801

_failures: list[str] = []


# --------------------------------------------------------------------------- #
# 检查工具
# --------------------------------------------------------------------------- #
def check(condition: bool, label: str) -> bool:
    """记录一条检查结果。"""
    print(("  [PASS] " if condition else "  [FAIL] ") + label, flush=True)
    if not condition:
        _failures.append(label)
    return condition


def title(text: str) -> None:
    print("\n" + "=" * 74)
    print(text)
    print("=" * 74, flush=True)


def child_env() -> dict:
    """给子进程统一 UTF-8：否则中文日志在 Windows 上会按 GBK 出来变成乱码。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_gateway(args: list[str], stdin_text: str = "") -> tuple[list[dict], str, int]:
    """跑 run_gateway.py，返回 (逐行解析出的决策, stderr, 退出码)。

    任何一行输出不是合法 JSON 都会直接抛异常 —— 这正是「严格合法」的含义。
    """
    proc = subprocess.run(
        [sys.executable, "run_gateway.py", *args],
        cwd=str(SKELETON),
        input=stdin_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=TIMEOUT,
        env=child_env(),
    )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    return parsed, proc.stderr.strip(), proc.returncode


def check_decisions(decisions: list[dict], label: str) -> None:
    """对一批决策做通用的协议校验。"""
    check(bool(decisions), f"{label}: 有输出")
    check(
        all(isinstance(d, dict) and set(d) == {"time", "option"} for d in decisions),
        f"{label}: 每行恰好 time + option 两个键",
    )
    check(
        all(isinstance(d.get("time"), str) and d["time"] for d in decisions),
        f"{label}: time 是非空字符串",
    )
    check(
        all(d.get("option") in OPTIONS for d in decisions),
        f"{label}: option 只在 {'/'.join(OPTIONS)} 里",
    )


def count_request_lines(path: Path) -> tuple[int, int, list[str | None]]:
    """统计样本文件：非空行数、不是 JSON 的行数、每行期望的 time（坏行为 None）。"""
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = 0
    expected: list[str | None] = []
    for line in lines:
        try:
            parsed = json.loads(line)
        except ValueError:
            bad += 1
            expected.append(None)
            continue
        expected.append(parsed.get("time") if isinstance(parsed, dict) else None)
    return len(lines), bad, expected


# --------------------------------------------------------------------------- #
# (a) 离线兜底
# --------------------------------------------------------------------------- #
def scenario_offline() -> None:
    title("(a) 离线兜底：run_gateway.py --offline")
    requests = ['{"time":"t1"}', '{"time":"t2","history":["rock"]}']
    decisions, stderr, code = run_gateway(["--offline", "--quiet"], "\n".join(requests) + "\n")
    for item in decisions:
        print("     " + json.dumps(item, ensure_ascii=False))

    check_decisions(decisions, "(a)")
    check(len(decisions) == len(requests), "(a): 一行进一行出（2 行进，2 行出）")
    check([d["time"] for d in decisions] == ["t1", "t2"], "(a): time 与输入逐行对齐")
    check(
        decisions[1]["option"] == "paper",
        "(a): history=[rock] 时本地兜底出布（布赢石头）",
    )
    check(decisions[0]["option"] == "rock", "(a): 没有历史时兜底出 rock")
    check(code == 0, f"(a): 退出码为 0（实际 {code}）")
    check("本地兜底 2" in stderr, "(a): 统计显示 2 行都走了本地兜底")


# --------------------------------------------------------------------------- #
# (b) 坏上游也不许崩
# --------------------------------------------------------------------------- #
def scenario_bad_upstream() -> None:
    title("(b) 坏上游也不许崩：mock_llm_server.py + samples/requests.jsonl")
    samples = SKELETON / "samples" / "requests.jsonl"
    total, bad, expected = count_request_lines(samples)
    print(f"     samples/requests.jsonl：{total} 个非空行，其中 {bad} 行不是 JSON")

    sys.path.insert(0, str(SKELETON))
    from mock_llm_server import MockLlmServer  # noqa: E402 - 需要先补 sys.path

    with MockLlmServer() as server:
        decisions, stderr, code = run_gateway(
            [
                "--api-base-url", server.base_url,
                "--api-key", "test",
                "--input", "samples/requests.jsonl",
                "--quiet",
            ]
        )
        for item in decisions:
            print("     " + json.dumps(item, ensure_ascii=False))

        check_decisions(decisions, "(b)")
        check(len(decisions) == total, f"(b): 一行进一行出（{total} 行进，{len(decisions)} 行出）")
        aligned = all(
            want is None or got["time"] == want
            for got, want in zip(decisions, expected)
        )
        check(aligned, "(b): 有 time 的请求逐行对齐（模型自报的 time 被丢弃）")
        check(
            all(d["time"] for d in decisions),
            "(b): 缺 time / 坏输入的那两行也补上了时间",
        )
        # 假上游每条回复的 reasoning_content 里都写死 option=rock
        options = {d["option"] for d in decisions}
        check(options != {"rock"}, f"(b): 没有误用思维链（实测 option 集合 {sorted(options)}）")
        check(
            all(r["auth"] == "Bearer test" for r in server.requests),
            "(b): 每个请求都带 Authorization: Bearer",
        )
        check(
            all(r["response_format"] == {"type": "json_object"} for r in server.requests),
            "(b): 开了 response_format=json_object",
        )
        check(
            all(r["thinking"] == {"type": "disabled"} for r in server.requests),
            "(b): 默认关闭思考模式",
        )
        check(
            all("这不是 JSON" not in r["user_text"] for r in server.requests),
            "(b): 非 JSON 的那行没有被转发给上游（不浪费钱）",
        )
        check(code == 0, f"(b): 退出码为 0（实际 {code}）")
        check("输入非法 1" in stderr, "(b): 统计显示有 1 行输入非法")

    # 空回复必须触发重试：只给 2 条预设坏回复，第 1 条就是空回复
    with MockLlmServer(scenarios=["", '{"time": "{time}", "option": "paper"}']) as server:
        decisions, _, _ = run_gateway(
            ["--api-base-url", server.base_url, "--api-key", "test", "--quiet"],
            '{"time": "t"}\n',
        )
        shown = json.dumps(decisions[0], ensure_ascii=False) if decisions else "无输出"
        print(f"     空回复重试 -> {shown}（上游收到 {len(server.requests)} 个请求）")
        check(
            len(server.requests) == 2 and decisions == [{"time": "t", "option": "paper"}],
            "(b): 空回复触发一次重试后拿到 paper",
        )


# --------------------------------------------------------------------------- #
# (c) 完整对局
# --------------------------------------------------------------------------- #
def scenario_play_game(rounds: int, real_api: bool) -> None:
    if real_api:
        title(f"(c) 完整对局（真实 DeepSeek API）：play_game.py --rounds {rounds}")
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not check(bool(key), "(c): 环境变量 DEEPSEEK_API_KEY 已设置"):
            return
        args = [sys.executable, "play_game.py", "--rounds", str(rounds), "--quiet"]
        server = None
    else:
        title(f"(c) 完整对局（本地假上游）：play_game.py --rounds {rounds}")
        sys.path.insert(0, str(SKELETON))
        from mock_llm_server import MockLlmServer  # noqa: E402

        server = MockLlmServer()
        server.start()
        args = [
            sys.executable, "play_game.py", "--rounds", str(rounds),
            "--api-base-url", server.base_url, "--api-key", "test", "--quiet",
        ]

    try:
        proc = subprocess.run(
            args,
            cwd=str(SKELETON),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=TIMEOUT,
            env=child_env(),
        )
        out = proc.stdout
        print("     " + out.strip().replace("\n", "\n     "))
        check(f"共 {rounds} 轮" in out, f"(c): 打满 {rounds} 轮")
        check(("模型赢" in out) and ("平" in out) and ("输" in out), "(c): 有完整记分")
        check(proc.returncode == 0, f"(c): 退出码为 0（实际 {proc.returncode}）")
        if server is not None:
            strings = [request.get("user_text") or "" for request in server.requests]
            check(
                len(server.requests) >= rounds,
                f"(c): 假上游至少收到 {rounds} 个请求（实际 {len(server.requests)}，多出来的是空回复重试）",
            )
            check(
                all('"time"' in text for text in strings),
                "(c): 每个请求都带 time 字段",
            )
            check(
                sum(1 for text in strings if '"history"' in text) >= rounds - 1,
                "(c): 第 2 轮起请求都带上了对手历史 history",
            )
    finally:
        if server is not None:
            server.stop()


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="任务书三条验收命令 + 严格输出校验")
    parser.add_argument("--rounds", type=int, default=10, help="对局轮数，默认 10")
    parser.add_argument(
        "--real-api",
        action="store_true",
        help="(c) 用真实 DeepSeek API（读 DEEPSEEK_API_KEY）而不是本地假上游",
    )
    parser.add_argument("--skip", choices=["a", "b", "c"], action="append", default=[],
                        help="跳过某条场景，可重复")
    args = parser.parse_args(argv)

    print("石头剪刀布决策网关 · 一键验收")
    print(f"skeleton 目录：{SKELETON}")
    if not SKELETON.is_dir():
        print(f"找不到 {SKELETON}，请把本脚本放在仓库根目录（与 skeleton/ 同级）")
        return 2

    try:
        if "a" not in args.skip:
            scenario_offline()
        if "b" not in args.skip:
            scenario_bad_upstream()
        if "c" not in args.skip:
            scenario_play_game(args.rounds, args.real_api)
    except json.JSONDecodeError as exc:
        _failures.append(f"有输出行不是合法 JSON：{exc}")
        print(f"\n  [FAIL] 有输出行不是合法 JSON：{exc}")

    title("验收结果")
    if _failures:
        print(f"❌ {len(_failures)} 项失败：")
        for item in _failures:
            print("   - " + item)
        return 1
    print("✅ 全部通过：三条验收命令都跑通，输出每行都是严格合法的决策 JSON")
    return 0


if __name__ == "__main__":
    sys.exit(main())
