# Week 4 run - retriever: dense (top-3)

hit-rate@3: **8/12**   p50 latency: **813.7 ms**


## Q1: What is noi arisi?
expected `ragi-koozh-05::structure::1` - **HIT at rank 1** (731.5 ms)

1. `ragi-koozh-05::structure::1` score=0.282
   > # Ragi Koozh (fermented finger-millet porridge) ## Ingredients | Ingredient | Weight | % of ragi | |---|---|---| | Ragi (finger millet) flour | 300g | 100% | | Broken rice (noi arisi) | 100g | 33% | | Water | 1500g | 500...

2. `appam-03::structure::1` score=0.247
   > # Appam (lace-edged fermented rice hoppers) ## Ingredients | Ingredient | Weight | % of rice | |---|---|---| | Raw rice (pachari), soaked | 500g | 100% | | Cooked rice | 100g | 20% | | Fresh thick coconut milk | 400g | 8...

3. `idli-batter-01::structure::3` score=0.240
   > # Idli Batter (2kg batch) ## Allergen note Naturally vegan and gluten-free. If adding asafoetida (hing), check the label — most Indian brands are bound with wheat flour....


## Q2: What can I cook in an appachatti?
expected `appam-03::structure::2` - **HIT at rank 1** (840.9 ms)

1. `appam-03::structure::2` score=0.428
   > # Appam (lace-edged fermented rice hoppers) ## Method Soak the raw rice 4 hours, then grind with the cooked rice and half the coconut milk to a completely smooth batter. Stir in the toddy (or the yeast mixture) and the s...

2. `dosa-batter-02::structure::2` score=0.425
   > # Crisp Dosa Batter ## Method Soak rice, urad dal, chana dal and fenugreek together for 5 hours; soak the poha separately for the last 30 minutes. Grind everything to a smooth, flowing batter — thinner than idli batter —...

3. `appam-03::structure::1` score=0.371
   > # Appam (lace-edged fermented rice hoppers) ## Ingredients | Ingredient | Weight | % of rice | |---|---|---| | Raw rice (pachari), soaked | 500g | 100% | | Cooked rice | 100g | 20% | | Fresh thick coconut milk | 400g | 8...


## Q3: What is kannimanga?
expected `kadumanga-06::structure::1` - **HIT at rank 1** (854.4 ms)

1. `kadumanga-06::structure::1` score=0.339
   > # Kadumanga Achar (Kerala fermented tender mango pickle) ## Ingredients | Ingredient | Weight | % of mango | |---|---|---| | Tender baby mangoes (kannimanga), whole | 1000g | 100% | | Crystal sea salt | 150g | 15% | | Ka...

2. `kadumanga-06::structure::0` score=0.314
   > # Kadumanga Achar (Kerala fermented tender mango pickle) Percentages are relative to the mango weight (100%)....

3. `kadumanga-06::structure::3` score=0.275
   > # Kadumanga Achar (Kerala fermented tender mango pickle) ## Allergen note Contains sesame (gingelly oil) and mustard. Most asafoetida is bound with wheat flour — use a certified gluten-free hing or omit it for gluten-fre...


## Q4: What ingredient is 6.7% of the rice weight?
expected `dosa-batter-02::structure::1` - **MISS** (865.2 ms)

1. `appam-03::structure::0` score=0.649
   > # Appam (lace-edged fermented rice hoppers) Percentages are relative to the raw rice weight (100%)....

2. `idli-batter-01::structure::0` score=0.646
   > # Idli Batter (2kg batch) Percentages are relative to the rice weight (100%)....

3. `appam-03::structure::1` score=0.616
   > # Appam (lace-edged fermented rice hoppers) ## Ingredients | Ingredient | Weight | % of rice | |---|---|---| | Raw rice (pachari), soaked | 500g | 100% | | Cooked rice | 100g | 20% | | Fresh thick coconut milk | 400g | 8...


## Q5: What is 72% of the rice weight in one of the batters?
expected `idli-batter-01::structure::1` - **MISS** (937.6 ms)

1. `dosa-batter-02::structure::0` score=0.756
   > # Crisp Dosa Batter Percentages are relative to the rice weight (100%)....

2. `idli-batter-01::structure::0` score=0.740
   > # Idli Batter (2kg batch) Percentages are relative to the rice weight (100%)....

3. `appam-03::structure::0` score=0.614
   > # Appam (lace-edged fermented rice hoppers) Percentages are relative to the raw rice weight (100%)....


## Q6: My dosas keep sticking to the pan - what am I doing wrong?
expected `dosa-batter-02::structure::2` - **HIT at rank 1** (786.1 ms)

1. `dosa-batter-02::structure::2` score=0.491
   > # Crisp Dosa Batter ## Method Soak rice, urad dal, chana dal and fenugreek together for 5 hours; soak the poha separately for the last 30 minutes. Grind everything to a smooth, flowing batter — thinner than idli batter —...

2. `dosa-batter-02::structure::0` score=0.370
   > # Crisp Dosa Batter Percentages are relative to the rice weight (100%)....

3. `dosa-batter-02::structure::1` score=0.359
   > # Crisp Dosa Batter ## Ingredients | Ingredient | Weight | % of rice | |---|---|---| | Dosa rice (raw, short-grain) | 750g | 100% | | Whole white urad dal | 250g | 33% | | Chana dal | 30g | 4% | | Fenugreek seeds | 8g | ...


## Q7: How do I know the urad dal has been ground enough?
expected `idli-batter-01::structure::2` - **HIT at rank 1** (718.1 ms)

1. `idli-batter-01::structure::2` score=0.454
   > # Idli Batter (2kg batch) ## Method Wash and soak the rice and the urad dal separately for 4 to 6 hours, with the fenugreek seeds in the dal bowl. Grind the dal first with ice-cold water until light, fluffy and tripled i...

2. `dosa-batter-02::structure::2` score=0.391
   > # Crisp Dosa Batter ## Method Soak rice, urad dal, chana dal and fenugreek together for 5 hours; soak the poha separately for the last 30 minutes. Grind everything to a smooth, flowing batter — thinner than idli batter —...

3. `dosa-batter-02::structure::1` score=0.329
   > # Crisp Dosa Batter ## Ingredients | Ingredient | Weight | % of rice | |---|---|---| | Dosa rice (raw, short-grain) | 750g | 100% | | Whole white urad dal | 250g | 33% | | Chana dal | 30g | 4% | | Fenugreek seeds | 8g | ...


## Q8: Why did my curd become too sour by the evening?
expected `thayir-04::structure::2` - **HIT at rank 1** (760.1 ms)

1. `thayir-04::structure::2` score=0.522
   > # Thayir — Homemade Curd (set overnight) ## Method Bring the milk just to a boil, then simmer 5 minutes to concentrate it slightly — this gives a thicker set. Cool to 40–43°C: the milk should feel distinctly warm, not ho...

2. `thayir-04::structure::0` score=0.407
   > # Thayir — Homemade Curd (set overnight) Percentages are relative to the milk weight (100%)....

3. `thayir-04::structure::1` score=0.329
   > # Thayir — Homemade Curd (set overnight) ## Ingredients | Ingredient | Weight | % of milk | |---|---|---| | Whole milk (full-fat) | 1000g | 100% | | Live curd from the previous batch | 30g | 3% |...


## Q9: How long until the mango pickle is ready to eat?
expected `kadumanga-06::structure::2` - **HIT at rank 1** (797.9 ms)

1. `kadumanga-06::structure::2` score=0.640
   > # Kadumanga Achar (Kerala fermented tender mango pickle) ## Method Wipe the mangoes dry — no water must touch them at any stage. Layer them with the crystal salt in a sterilised bharani (ceramic pickle jar), close, and s...

2. `kadumanga-06::structure::1` score=0.480
   > # Kadumanga Achar (Kerala fermented tender mango pickle) ## Ingredients | Ingredient | Weight | % of mango | |---|---|---| | Tender baby mangoes (kannimanga), whole | 1000g | 100% | | Crystal sea salt | 150g | 15% | | Ka...

3. `kadumanga-06::structure::0` score=0.467
   > # Kadumanga Achar (Kerala fermented tender mango pickle) Percentages are relative to the mango weight (100%)....


## Q10: Which recipe has the highest salt percentage?
expected `kadumanga-06::structure::1` - **MISS** (748.8 ms)

1. `ragi-koozh-05::structure::1` score=0.496
   > # Ragi Koozh (fermented finger-millet porridge) ## Ingredients | Ingredient | Weight | % of ragi | |---|---|---| | Ragi (finger millet) flour | 300g | 100% | | Broken rice (noi arisi) | 100g | 33% | | Water | 1500g | 500...

2. `ragi-koozh-05::structure::0` score=0.443
   > # Ragi Koozh (fermented finger-millet porridge) Percentages are relative to the ragi flour weight (100%)....

3. `dosa-batter-02::structure::0` score=0.439
   > # Crisp Dosa Batter Percentages are relative to the rice weight (100%)....


## Q11: Which batter should be thinner than idli batter?
expected `dosa-batter-02::structure::2` - **MISS** (831.3 ms)

1. `idli-batter-01::structure::0` score=0.590
   > # Idli Batter (2kg batch) Percentages are relative to the rice weight (100%)....

2. `idli-batter-01::structure::1` score=0.567
   > # Idli Batter (2kg batch) ## Ingredients | Ingredient | Weight | % of rice | |---|---|---| | Idli rice (parboiled) | 1000g | 100% | | Whole white urad dal | 250g | 25% | | Fenugreek seeds | 10g | 1% | | Rock salt | 20g |...

3. `dosa-batter-02::structure::0` score=0.536
   > # Crisp Dosa Batter Percentages are relative to the rice weight (100%)....


## Q12: What gives dosa its crispness?
expected `dosa-batter-02::structure::1` - **HIT at rank 1** (829.4 ms)

1. `dosa-batter-02::structure::1` score=0.682
   > # Crisp Dosa Batter ## Ingredients | Ingredient | Weight | % of rice | |---|---|---| | Dosa rice (raw, short-grain) | 750g | 100% | | Whole white urad dal | 250g | 33% | | Chana dal | 30g | 4% | | Fenugreek seeds | 8g | ...

2. `dosa-batter-02::structure::0` score=0.625
   > # Crisp Dosa Batter Percentages are relative to the rice weight (100%)....

3. `dosa-batter-02::structure::2` score=0.520
   > # Crisp Dosa Batter ## Method Soak rice, urad dal, chana dal and fenugreek together for 5 hours; soak the poha separately for the last 30 minutes. Grind everything to a smooth, flowing batter — thinner than idli batter —...
