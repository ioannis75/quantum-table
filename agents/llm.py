"""Model access with fallbacks. Returns (text, label) or raises. API keys are read only here and never logged.
NOTE: the Anthropic path follows the public SDK; the Oumi path is a best-effort OpenAI-compatible call and is UNTESTED here
(no key, host not reachable from the build box)."""
import os
import config

ANTHROPIC_MODELS = {"smart": "claude-sonnet-5-5", "fast": "claude-haiku-5-5"}


class NoModel(Exception):
    pass


def anthropic_ask(system: str, user: str, tier: str = "smart", max_tokens: int = 700, timeout: float = 25.0):
    if not config.has("ANTHROPIC_API_KEY"):
        raise NoModel("no ANTHROPIC_API_KEY")
    import anthropic
    c = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=timeout)
    model = ANTHROPIC_MODELS[tier]
    r = c.messages.create(model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text"), f"Claude ({model})"


def oumi_ask(system: str, user: str, max_tokens: int = 700, timeout: float = 25.0):
    if not (config.has("OUMI_API_KEY") and config.has("OUMI_DEPLOYMENT_ID")):
        raise NoModel("no OUMI key/deployment")
    from openai import OpenAI
    c = OpenAI(base_url="https://api.oumi.ai/inference/v1", api_key=os.environ["OUMI_API_KEY"], timeout=timeout)
    r = c.chat.completions.create(model=os.environ["OUMI_DEPLOYMENT_ID"], max_tokens=max_tokens,
                                  messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return r.choices[0].message.content, "Oumi"


def ask_with_fallback(chain: list, system: str, user: str, **kw):
    """chain: list of callables taking (system,user,**kw). First that works wins; raises NoModel if none."""
    last = None
    for fn in chain:
        try:
            return fn(system, user, **kw)
        except Exception as e:   # unreachable host, bad key, rate limit ...
            last = e
    raise NoModel(str(last))
