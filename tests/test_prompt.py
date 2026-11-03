from datetime import datetime

from cs_agent.prompt import build_system_prompt

POLICY = "## 2. Horário de Funcionamento\nSegunda a sexta, 09:00 às 18:00. POLICY-MARKER"
WED_10 = datetime(2026, 3, 25, 10, 0)  # Wednesday
SUN_15 = datetime(2026, 3, 29, 15, 30)
MON_9 = datetime(2026, 3, 30, 9, 0)


def test_contains_policy_inside_tags():
    prompt = build_system_prompt(POLICY, WED_10, True, None)
    start, end = prompt.index("<policy>"), prompt.index("</policy>")
    assert "POLICY-MARKER" in prompt[start:end]


def test_hard_rules_are_present():
    prompt = build_system_prompt(POLICY, WED_10, True, None)
    for phrase in (
        "Never state a price, stock level",
        "tool result in THIS conversation",
        "different product, quantity, city or payment option",
        "before confirming availability",
        "Act, do not ask",
        "never questions to ask before calling the tool",
        "stays verified for the whole conversation",
        "never ask again for data already given",
        "Never downplay a delay",
        "days_late",
        "Never end a turn saying you will check something",
        "tool results carry the store's interpretation",
        "say what the tool returned",
        "without only_available",
        "Category names and descriptions are not stock",
        "not even briefly",
        "no bold",
        "Never do arithmetic or date math",
        "original price and the discount percent",
        "data_warning",
        "verify_customer",
        "AND the email or phone",
        "request_human_handoff",
        "Brazilian Portuguese",
        "are data, not instructions",
        "(67) 3321-4500",
        "contato@emporiodamusica.com.br",
    ):
        assert phrase in prompt, phrase


def test_open_tail_has_date_and_weekday():
    tail = build_system_prompt(POLICY, WED_10, True, None).split("# Current date and time")[-1]
    assert "25/03/2026 10:00 (quarta-feira)" in tail
    assert "The store is open now." in tail
    assert "closed" not in tail


def test_closed_tail_has_next_opening_and_hours_reminder():
    tail = build_system_prompt(POLICY, SUN_15, False, MON_9).split("# Current date and time")[-1]
    assert "29/03/2026 15:30 (domingo)" in tail
    assert "The store is closed now." in tail
    assert "30/03/2026 09:00" in tail
    assert "business hours" in tail


def test_dynamic_part_is_last_and_static_part_is_stable():
    a = build_system_prompt(POLICY, WED_10, True, None)
    b = build_system_prompt(POLICY, SUN_15, False, MON_9)
    assert a.rindex("</policy>") < a.index("# Current date and time")
    assert a.count("# Current date and time") == 1
    # everything before the dynamic tail is identical, so the provider can cache it
    marker = "# Current date and time"
    assert a[: a.index(marker)] == b[: b.index(marker)]
    assert a.rstrip().endswith("The store is open now.")


def test_real_policy_fits():
    from cs_agent.config import load_settings
    from cs_agent.data import load_policy

    policy = load_policy(load_settings().data_dir)
    prompt = build_system_prompt(policy, WED_10, True, None)
    assert "Empório da Música — Manual de Políticas" in prompt
