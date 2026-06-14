from openai import OpenAI
from pokerbot import config

c = OpenAI(api_key=config.OPENAI_API_KEY)
ids = sorted(m.id for m in c.models.list().data)
hits = [m for m in ids if ("gpt-5" in m) or m.startswith("o3") or m.startswith("o4") or ("gpt-4" in m)]
print("reasoning/frontier models available:")
for m in hits:
    print(" ", m)
print("gpt-5.5 present:", any("5.5" in m or "5-5" in m for m in ids))
