"""Command-line chat with the agent: interactive loop (script and transcript modes below)."""

import argparse
import json
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time

from cs_agent.agent import Agent, AgentReply, ToolTrace
from cs_agent.app import build_agent
from cs_agent.config import PROJECT_ROOT, Settings, load_settings, parse_reference_date
from cs_agent.llm import PROVIDERS, ConfigError
from cs_agent.rules.hours import is_open

LOG_FILE = PROJECT_ROOT / "cs-agent.log"
PROMPT = "você> "
TRACE_RESULT_CHARS = 400
EXIT_USAGE = 2  # same code argparse uses for bad arguments

HELP = """\
Comandos:
  /ajuda   mostra esta lista
  /reset   começa uma nova conversa
  /debug   liga ou desliga o rastro das ferramentas
  /sair    encerra (também /exit, Ctrl+D)"""


# --- arguments ---------------------------------------------------------------------------


def _date_arg(value: str) -> date:
    try:
        if not value.strip():
            raise ValueError
        return parse_reference_date(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid date {value!r}: use YYYY-MM-DD or 'today'"
        ) from None


def _time_arg(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid time {value!r}: use HH:MM") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cs-agent", description="Chat with the Empório da Música customer service agent."
    )
    parser.add_argument("--debug", action="store_true", help="show every tool call and result")
    parser.add_argument(
        "--date", type=_date_arg, metavar="YYYY-MM-DD|today", help="override REFERENCE_DATE"
    )
    parser.add_argument(
        "--time", type=_time_arg, metavar="HH:MM", help="pin the clock (default: real time)"
    )
    parser.add_argument("--provider", choices=sorted(PROVIDERS), help="override LLM_PROVIDER")
    parser.add_argument("--model", metavar="NAME", help="override LLM_MODEL")
    return parser


def apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    changes: dict[str, object] = {}
    if args.date:
        changes["reference_date"] = args.date
    if args.provider:
        changes["llm_provider"] = args.provider
        if args.provider != settings.llm_provider:
            changes["llm_model"] = None  # LLM_MODEL names a model of the other provider
    if args.model:
        changes["llm_model"] = args.model
    return replace(settings, **changes)


# --- logging -----------------------------------------------------------------------------


class _ConsoleWarnings(logging.Handler):
    """While debugging, show a logged failure as one line. The traceback goes to the log file."""

    def __init__(self, enabled: Callable[[], bool]):
        super().__init__(logging.WARNING)
        self.enabled = enabled

    def emit(self, record: logging.LogRecord) -> None:
        if not self.enabled():
            return
        line = record.getMessage()
        if record.exc_info and record.exc_info[1] is not None:
            error = " ".join(str(record.exc_info[1]).split())[:200]
            line += f" ({type(record.exc_info[1]).__name__}: {error})"
        print(f"  ⚠ {line}")


_handlers: list[logging.Handler] = []


def configure_logging(is_debug: Callable[[], bool]) -> None:
    """WARNING and above go to the log file, never to the chat (except `_ConsoleWarnings`)."""
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", delay=True)
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    for handler in (file_handler, _ConsoleWarnings(is_debug)):
        root.addHandler(handler)
        _handlers.append(handler)
    root.setLevel(logging.WARNING)


def shutdown_logging() -> None:
    root = logging.getLogger()
    while _handlers:
        handler = _handlers.pop()
        root.removeHandler(handler)
        handler.close()


# --- chat --------------------------------------------------------------------------------


@dataclass
class Options:
    debug: bool


def _compact(result: dict, limit: int) -> str:
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_call(trace: ToolTrace) -> str:
    if isinstance(trace.args, dict):
        args = ", ".join(f"{key}={value!r}" for key, value in trace.args.items())
    else:
        args = str(trace.args)  # the model sent arguments that are not valid JSON
    return f"{trace.name}({args})"


class Chat:
    """One conversation on the terminal."""

    def __init__(self, agent: Agent, options: Options):
        self.agent = agent
        self.options = options

    def banner(self) -> None:
        ctx = self.agent.ctx
        clock = "fixa" if ctx.fixed_time else "relógio real"
        store = "aberta" if is_open(ctx.now) else "fechada"
        print("Empório da Música · assistente virtual")
        print(f"Modelo: {self.agent.llm.provider} / {self.agent.llm.model}")
        print(f"Data de referência: {ctx.now:%d/%m/%Y} · hora: {ctx.now:%H:%M} ({clock})")
        print(f"Loja: {store} agora")
        print("/ajuda para comandos\n")

    def handle(self, line: str) -> bool:
        """Process one input line. Returns False when the session must end."""
        text = line.strip()
        if not text:
            return True
        if text.startswith("/"):
            return self._command(text.lower())
        return self._message(text)

    def _command(self, command: str) -> bool:
        if command in ("/sair", "/exit"):
            return False
        if command == "/ajuda":
            print(HELP)
        elif command == "/reset":
            self.agent.reset()
            print("Conversa reiniciada.")
        elif command == "/debug":
            self.options.debug = not self.options.debug
            print(f"Debug {'ligado' if self.options.debug else 'desligado'}.")
        else:
            print("Comando desconhecido. /ajuda para comandos.")
        return True

    def _message(self, text: str) -> bool:
        try:
            reply = self.agent.reply(text)
        except KeyboardInterrupt:
            # The turn is half done and the history with it: end the session instead.
            print("\nInterrompido.")
            return False
        if self.options.debug:
            self._print_trace(reply)
        print(f"assistente> {reply.text}")
        return True

    @staticmethod
    def _print_trace(reply: AgentReply) -> None:
        for trace in reply.trace:
            print(f"  🔧 {_format_call(trace)} · {trace.ms:.0f} ms")
            print(f"     {_compact(trace.result, TRACE_RESULT_CHARS)}")
        if reply.fallback:
            print("  ⚠ fallback")


def run_interactive(chat: Chat) -> None:
    chat.banner()
    while True:
        try:
            line = input(PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not chat.handle(line):
            break
    print("Até logo!")


def _enable_readline() -> None:
    try:
        import readline  # noqa: F401  (arrow keys and history in input())
    except ImportError:  # Windows
        pass


def _fail(message: str) -> int:
    print(f"cs-agent: error: {message}", file=sys.stderr)
    return EXIT_USAGE


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)  # exits with code 2 on invalid arguments
    try:
        settings = apply_overrides(load_settings(), args)
    except ValueError as e:  # invalid REFERENCE_DATE in .env
        return _fail(str(e))
    try:
        agent = build_agent(settings, fixed_time=args.time)
    except ConfigError as e:
        return _fail(str(e))

    options = Options(debug=args.debug)
    configure_logging(lambda: options.debug)
    _enable_readline()
    try:
        run_interactive(Chat(agent, options))
    finally:
        shutdown_logging()
    return 0
