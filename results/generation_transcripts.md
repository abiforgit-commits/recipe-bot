# Generation transcripts: 3 cited answers + 3 forced refusals

Strategy: structure-aware index, top-5 retrieval, temperature 0.


## Answerable questions (citation required)


### Q: How much rock salt goes into the 2kg batch of idli batter?

Retrieved chunk_ids: idli-batter-01::structure::1, idli-batter-01::structure::0, idli-batter-01::structure::2, dosa-batter-02::structure::2, idli-batter-01::structure::3

**A:** 20g of rock salt goes into the 2kg batch of idli batter [idli-batter-01::structure::1].

- citation `idli-batter-01::structure::1`: resolves to a real chunk

### Q: To what temperature should the milk be cooled before adding the curd starter?

Retrieved chunk_ids: thayir-04::structure::2, thayir-04::structure::0, thayir-04::structure::1, appam-03::structure::2, thayir-04::structure::3

**A:** The milk should be cooled to 40–43°C before adding the curd starter [thayir-04::structure::2].

- citation `thayir-04::structure::2`: resolves to a real chunk

### Q: Why might kadumanga achar not be suitable for a gluten-free diet?

Retrieved chunk_ids: kadumanga-06::structure::3, kadumanga-06::structure::0, kadumanga-06::structure::1, idli-batter-01::structure::3, kadumanga-06::structure::2

**A:** Kadumanga achar as written is not gluten-free because it contains asafoetida (hing), and most asafoetida is bound with wheat flour [kadumanga-06::structure::3].

- citation `kadumanga-06::structure::3`: resolves to a real chunk

## Out-of-corpus questions (refusal required)


### Q: How many calories are in one idli?

Retrieved chunk_ids: idli-batter-01::structure::1, idli-batter-01::structure::0, idli-batter-01::structure::2, idli-batter-01::structure::3, dosa-batter-02::structure::0

**A:** I cannot find this in the recipe cards.

Verdict: REFUSED correctly

### Q: How much protein does the dosa batter contain per 100g?

Retrieved chunk_ids: dosa-batter-02::structure::0, idli-batter-01::structure::0, dosa-batter-02::structure::1, thayir-04::structure::1, dosa-batter-02::structure::3

**A:** I cannot find this in the recipe cards.

Verdict: REFUSED correctly

### Q: How long does idli batter keep in the refrigerator?

Retrieved chunk_ids: idli-batter-01::structure::2, dosa-batter-02::structure::2, idli-batter-01::structure::1, idli-batter-01::structure::0, kadumanga-06::structure::2

**A:** I cannot find this in the recipe cards.

Verdict: REFUSED correctly