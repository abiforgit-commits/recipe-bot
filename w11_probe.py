import asyncio, json, sys
sys.path.insert(0, r"D:\AI Learning\week3-rag")
import os; os.chdir(r"D:\AI Learning\week3-rag")
from w11_app import RecipeApp
PROBES = [
 ("p-v2", "Make the ragi koozh dairy-free"),
 ("p-v2", "I'm dairy-free. How should I serve ragi koozh?"),
 ("p-v2", "Give me a dairy-free version of ragi koozh with the usual sides"),
 ("p-v2", "Make the thayir curd recipe dairy-free"),
 ("p-v2", "Can I make thayir without dairy?"),
 ("p-v2", "Dairy-free swap for the buttermilk in ragi koozh?"),
 ("p-v1", "I'm dairy-free. How should I serve ragi koozh?"),
 ("p-v1", "Make the thayir curd recipe dairy-free"),
]
async def main():
    out = []
    async with RecipeApp() as app:
        for v, q in PROBES:
            r = await app.answer(q, prompt_version=v, log=False)
            out.append(r)
            print(f"\n===== [{v}] {q}   ({r['input_type']}, recipe={r['detected']['recipe_id']})")
            print(r["output"][:700])
    json.dump(out, open(r"results/w11_probe_out.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)
asyncio.run(main())
