"""CLI tests: fake agent, monkeypatched input, no network and no real LLM."""

import logging
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace

import pytest

from cs_agent import cli
from cs_agent.agent import Agent, AgentReply, ToolTrace
from cs_agent.config import Settings
from cs_agent.data import load_store
from cs_agent.llm import LLM, ConfigError
from cs_agent.tools.context import ToolContext

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SETTINGS = Settings(
    llm_provider="gemini",
    llm_model="env-model",
    gemini_api_key=None,
    openai_api_key=None,
    ollama_base_url="http://localhost:11434/v1",
    data_dir=DATA_DIR,
    reference_date=date(2026, 3, 25),
)


class FakeAgent:
    """Stands in for Agent: replies from a queue; an Exception in the queue is raised."""

    def __init__(self, replies=(), now=datetime(2026, 3, 25, 10, 0)):
        self.replies = list(replies)
        self.received = []
        self.resets = 0
        self.llm = SimpleNamespace(provider="fake", model="fake-model")
        self.ctx = SimpleNamespace(now=now, ref_date=now.date(), fixed_time=now.time())

    def reply(self, text):
        self.received.append(text)
        item = self.replies.pop(0) if self.replies else AgentReply("ok")
        if isinstance(item, BaseException):
            raise item
        return item

    def reset(self):
        self.resets += 1


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Isolated CLI: fixed settings, a fake agent, a temporary log, scripted input."""
    state = SimpleNamespace(agent=FakeAgent(), built=[], consumed=[], settings=SETTINGS)

    def build_agent(settings, fixed_time=None):
        state.built.append((settings, fixed_time))
        return state.agent

    def feed(*lines):
        queue = list(lines)

        def fake_input(prompt=""):
            if not queue:
                raise EOFError
            item = queue.pop(0)
            state.consumed.append(item)
            if isinstance(item, BaseException):
                raise item
            return item

        monkeypatch.setattr("builtins.input", fake_input)

    monkeypatch.setattr(cli, "load_settings", lambda: state.settings)
    monkeypatch.setattr(cli, "build_agent", build_agent)
    monkeypatch.setattr(cli, "LOG_FILE", tmp_path / "cs-agent.log")
    state.feed = feed
    feed()  # default: Ctrl+D at the first prompt
    state.tmp = tmp_path
    return state


def trace(name="get_order", args=None, result=None, ms=3.2):
    return ToolTrace(name, {"order_id": 8} if args is None else args, result or {"status": "x"}, ms)


# --- arguments and startup -----------------------------------------------------------------


def test_overrides_reach_settings_and_clock(env):
    code = cli.main(
        ["--date", "2026-02-05", "--time", "10:00", "--provider", "ollama", "--model", "m"]
    )
    ((settings, fixed_time),) = env.built
    assert code == 0
    assert settings.reference_date == date(2026, 2, 5)
    assert (settings.llm_provider, settings.llm_model) == ("ollama", "m")
    assert fixed_time == time(10, 0)


def test_date_today_and_defaults(env):
    cli.main(["--date", "today"])
    cli.main([])
    (today, no_time), (default, _) = env.built
    assert today.reference_date == date.today() and no_time is None
    assert default == SETTINGS


def test_changing_provider_drops_the_model_of_the_old_one(env):
    cli.main(["--provider", "ollama"])
    cli.main(["--provider", "gemini"])
    assert env.built[0][0].llm_model is None
    assert env.built[1][0].llm_model == "env-model"


@pytest.mark.parametrize(
    "argv",
    [
        ["--date", "2026-13-01"],
        ["--date", ""],
        ["--time", "25:00"],
        ["--time", "10h"],
        ["--provider", "claude"],
    ],
)
def test_invalid_arguments_exit_2_without_traceback(env, capsys, argv):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(argv)
    assert exit_info.value.code == 2
    assert "Traceback" not in capsys.readouterr().err
    assert not env.built


def test_config_error_exits_2(env, monkeypatch, capsys):
    def broken(settings, fixed_time=None):
        raise ConfigError("needs an API key")

    monkeypatch.setattr(cli, "build_agent", broken)
    assert cli.main([]) == 2
    captured = capsys.readouterr()
    assert "needs an API key" in captured.err and "Traceback" not in captured.err
    assert captured.out == ""


def test_invalid_reference_date_in_env_exits_2(monkeypatch, capsys):
    def broken():
        raise ValueError("Invalid REFERENCE_DATE 'x'")

    monkeypatch.setattr(cli, "load_settings", broken)
    assert cli.main([]) == 2
    assert "Invalid REFERENCE_DATE" in capsys.readouterr().err


def test_missing_script_exits_2(env, tmp_path, capsys):
    assert cli.main(["--script", str(tmp_path / "nope.txt")]) == 2
    assert "cannot read script" in capsys.readouterr().err
    assert not env.built


def test_banner_shows_model_date_time_and_store_status(env, capsys):
    env.agent = FakeAgent(now=datetime(2026, 3, 25, 19, 30))
    cli.main([])
    out = capsys.readouterr().out
    assert "Empório da Música · assistente virtual" in out
    assert "fake / fake-model" in out
    assert "25/03/2026" in out and "19:30" in out
    assert "Loja: fechada" in out
    assert "/ajuda para comandos" in out
    env.agent = FakeAgent()
    cli.main([])
    assert "Loja: aberta" in capsys.readouterr().out


# --- interactive loop ----------------------------------------------------------------------


def test_message_gets_a_reply(env, capsys):
    env.agent.replies = [AgentReply("Oi! Como posso ajudar?")]
    env.feed("  Oi  ", "", "   ")
    assert cli.main([]) == 0
    assert env.agent.received == ["Oi"]  # blank lines are ignored
    out = capsys.readouterr().out
    assert "assistente> Oi! Como posso ajudar?" in out
    assert out.rstrip().endswith("Até logo!")


def test_reset_command(env, capsys):
    env.feed("/reset", "/RESET")
    cli.main([])
    assert env.agent.resets == 2 and env.agent.received == []
    assert capsys.readouterr().out.count("Conversa reiniciada.") == 2


def test_debug_command_toggles_the_trace(env, capsys):
    env.agent.replies = [AgentReply("a", [trace()]), AgentReply("b", [trace()]), AgentReply("c")]
    env.feed("1", "/debug", "2", "/debug", "3")
    cli.main([])
    out = capsys.readouterr().out
    assert out.count("🔧") == 1  # only the reply between the two /debug commands
    assert "Debug ligado." in out and "Debug desligado." in out


@pytest.mark.parametrize("command", ["/sair", "/exit", "/SAIR"])
def test_exit_commands_stop_the_session(env, command, capsys):
    env.feed("oi", command, "never read")
    assert cli.main([]) == 0
    assert env.consumed == ["oi", command]
    assert "Até logo!" in capsys.readouterr().out


def test_help_and_unknown_command(env, capsys):
    env.feed("/ajuda", "/nada")
    cli.main([])
    out = capsys.readouterr().out
    assert "/reset" in out and "/debug" in out and "/sair" in out
    assert "Comando desconhecido" in out
    assert env.agent.received == []  # a mistyped command is never sent to the model


@pytest.mark.parametrize("ending", [KeyboardInterrupt(), EOFError()])
def test_ctrl_c_and_ctrl_d_at_the_prompt_say_goodbye(env, ending, capsys):
    env.feed("oi", ending, "never read")
    assert cli.main([]) == 0
    assert env.consumed == ["oi", ending]
    assert "Até logo!" in capsys.readouterr().out


def test_ctrl_c_during_a_reply_ends_the_session_and_writes_the_transcript(env, capsys):
    env.agent.replies = [AgentReply("primeira"), KeyboardInterrupt()]
    env.feed("um", "dois", "never read")
    out_file = env.tmp / "deep" / "dir" / "t.md"
    assert cli.main(["--transcript", str(out_file)]) == 0
    assert env.consumed == ["um", "dois"]
    out = capsys.readouterr().out
    assert "Interrompido." in out and "Até logo!" in out
    text = out_file.read_text(encoding="utf-8")
    assert "primeira" in text and "dois" not in text  # the interrupted turn is not recorded


# --- debug trace ---------------------------------------------------------------------------


def test_debug_trace_format(env, capsys):
    long_result = {"text": "x" * 1000}
    env.agent.replies = [
        AgentReply("pronto", [trace(), trace("search_products", {"query": "violão"}, long_result)])
    ]
    env.feed("oi")
    cli.main(["--debug"])
    out = capsys.readouterr().out
    assert "  🔧 get_order(order_id=8) · 3 ms" in out
    assert "search_products(query='violão')" in out
    assert '{"status":"x"}' in out
    long_line = next(line for line in out.splitlines() if line.strip().startswith('{"text"'))
    assert len(long_line.strip()) == cli.TRACE_RESULT_CHARS and long_line.endswith("…")
    assert out.index("🔧") < out.index("assistente> pronto")


def test_debug_marks_fallback_replies(env, capsys):
    env.agent.replies = [
        AgentReply("Desculpe", [], fallback=True),
        AgentReply("Desculpe", [], True),
    ]
    env.feed("a")
    cli.main([])
    assert "assistente> Desculpe" in capsys.readouterr().out  # printed normally without debug
    env.feed("a")
    cli.main(["--debug"])
    assert "  ⚠ fallback" in capsys.readouterr().out


def test_invalid_json_arguments_are_shown_raw(env, capsys):
    env.agent.replies = [AgentReply("ok", [trace("get_order", "{broken")])]
    env.feed("a")
    cli.main(["--debug"])
    assert "get_order({broken)" in capsys.readouterr().out


# --- logging -------------------------------------------------------------------------------


def _agent_with_failing_llm():
    def fail(**kwargs):
        raise RuntimeError("boom")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
    ctx = ToolContext.create(load_store(DATA_DIR), date(2026, 3, 25), fixed_time=time(10, 0))
    return Agent(LLM(client, "fake-model", "fake"), ctx, "POLICY")


@pytest.mark.parametrize("argv", [[], ["--debug"]])
def test_logged_exceptions_never_print_a_traceback(env, capsys, argv):
    env.agent = _agent_with_failing_llm()
    env.feed("oi")
    handlers_before = list(logging.getLogger().handlers)
    assert cli.main(argv) == 0
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    assert "assistente> Desculpe" in captured.out
    assert ("⚠ Agent turn failed" in captured.out) == bool(argv)
    assert "RuntimeError: boom" in (env.tmp / "cs-agent.log").read_text(encoding="utf-8")
    assert logging.getLogger().handlers == handlers_before  # nothing leaks out of main()


# --- script parsing ------------------------------------------------------------------------

SCRIPT = """\
# Catálogo
# Busca de violões
#
# Segunda linha da descrição
# run: uv run cs-agent --script docs/scripts/01.txt --debug

Quero um violão

# comentário depois da primeira mensagem
/reset
#8 é o meu pedido
"""


def test_parse_script():
    script = cli.parse_script(SCRIPT)
    assert script.title == "Catálogo"
    assert script.description == ["Busca de violões", "", "Segunda linha da descrição"]
    assert script.command == "uv run cs-agent --script docs/scripts/01.txt --debug"
    assert script.lines == ["Quero um violão", "/reset", "#8 é o meu pedido"]


def test_parse_script_without_header():
    script = cli.parse_script("oi\ntudo bem?\n")
    assert (script.title, script.description, script.command) == (None, [], None)
    assert script.lines == ["oi", "tudo bem?"]


def test_script_mode_echoes_messages_and_resets(env, tmp_path, capsys):
    path = tmp_path / "s.txt"
    path.write_text(SCRIPT, encoding="utf-8")
    env.agent.replies = [AgentReply("Temos vários."), AgentReply("Anotado.")]
    assert cli.main(["--script", str(path)]) == 0
    assert env.agent.received == ["Quero um violão", "#8 é o meu pedido"]
    assert env.agent.resets == 1
    out = capsys.readouterr().out
    assert "Roteiro: Catálogo" in out
    assert "você> Quero um violão\nassistente> Temos vários." in out
    assert env.consumed == []  # never reads the keyboard


# --- transcripts ---------------------------------------------------------------------------


def run_script_with_transcript(env, tmp_path, argv=()):
    script = tmp_path / "s.txt"
    script.write_text(SCRIPT, encoding="utf-8")
    out_file = tmp_path / "out" / "t.md"
    env.agent.replies = [
        AgentReply("Temos vários.", [trace(), trace("get_product", {"product_id": 1}, {"a": "`"})]),
        AgentReply("Desculpe", [], fallback=True),
    ]
    cli.main(["--script", str(script), "--transcript", str(out_file), *argv])
    return out_file.read_text(encoding="utf-8")


def test_transcript_without_debug(env, tmp_path):
    text = run_script_with_transcript(env, tmp_path)
    assert text.startswith("# Catálogo\n\nBusca de violões\n\nSegunda linha da descrição\n")
    assert "*Model: fake / fake-model · Reference date: 2026-03-25 · Time: 10:00 (fixed)*" in text
    assert (
        "**How to reproduce**\n\n```\nuv run cs-agent --script docs/scripts/01.txt --debug\n```"
        in text
    )
    assert "**Cliente:** Quero um violão\n\n**Assistente:** Temos vários." in text
    assert "---\n\n*(nova conversa)*\n\n**Cliente:** #8 é o meu pedido" in text
    assert "<details>" not in text


def test_transcript_with_debug_lists_tool_calls(env, tmp_path):
    text = run_script_with_transcript(env, tmp_path, ["--debug"])
    assert "<details><summary>Ferramentas (2)</summary>" in text
    assert '- `get_order(order_id=8)` · 3 ms → `{"status":"x"}`' in text
    assert '- `get_product(product_id=1)` · 3 ms → `{"a":"\'"}`' in text  # no stray backticks
    assert "- ⚠ fallback" in text
    assert text.index("**Assistente:** Temos vários.") < text.index("<details>")


def test_transcript_without_header_or_command(env, tmp_path):
    script = tmp_path / "plain.txt"
    script.write_text("oi\n/reset\n/reset\n", encoding="utf-8")
    out_file = tmp_path / "t.md"
    cli.main(["--script", str(script), "--transcript", str(out_file)])
    text = out_file.read_text(encoding="utf-8")
    assert text.startswith("# plain\n\n*Model:")
    assert "How to reproduce" not in text
    assert text.count("(nova conversa)") == 1  # repeated resets collapse into one separator


def test_interactive_transcript_is_written_on_exit(env, tmp_path):
    out_file = tmp_path / "t.md"
    env.agent.replies = [AgentReply("Olá!")]
    env.feed("oi", "/sair")
    cli.main(["--transcript", str(out_file)])
    text = out_file.read_text(encoding="utf-8")
    assert text.startswith("# Conversa interativa")
    assert "**Cliente:** oi\n\n**Assistente:** Olá!" in text


def test_unwritable_transcript_exits_2_before_chatting(env, tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert cli.main(["--transcript", str(blocker / "t.md")]) == 2
    assert "cannot write transcript" in capsys.readouterr().err
    assert env.agent.received == []
