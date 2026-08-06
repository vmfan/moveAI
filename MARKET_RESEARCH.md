# MoveAI — Market Research

Sourced figures only. Every number below has a cited source; anything that is
a calculation built on top of a sourced figure is labeled **Derived** and
shows its arithmetic so the assumption can be checked or replaced. Nothing
here is a guess presented as a fact — where a search did not turn up a public
figure, that gap is stated explicitly rather than filled in.

This is a starting point for the Market + Competition slide of the pitch deck
(see `DESIGN.md` §"What the Final Pitch Deck Must Show"). Hong Kong figures are
in §1–§4; regional figures for mainland China, Japan, South Korea, Singapore
and Taiwan are in §5–§8.

**Source-quality grading.** Sections §5 onward carry a reliability grade per
figure, because this sector is heavily polluted by report-mill estimates. §8
gives concrete evidence of how bad they get, plus the citation rule to follow
when presenting live.

---

## 1. Hong Kong — market sizing inputs

| Figure | Value | Source |
|---|---|---|
| HK domestic households | **2.78 million** (May–Jul 2025 rolling estimate) | [C&SD General Household Survey](https://www.censtatd.gov.hk/en/page_235.html) |
| Residential property transactions, trailing 12 months (primary + secondary, private market) | **69,135** (23,390 primary + 45,745 secondary) | [Land Registry data via Centaline](https://hk.centanet.com/info/en/land-registry/12months) |
| Cost of a standard 5-person household move (North Point → Mei Foo, 40 furniture items + 20 cartons + 10 plastic boxes + 2 red-white-blue bags + 2 travel bags), across 20 surveyed companies | **HK$3,818 – HK$12,162**, average **HK$8,627** — a **3× spread** on an identical job; individual item-level charges differed by up to **141×** | [Consumer Council, 2024 survey of 20 removal companies](https://www.consumer.org.hk/tc/article/573-home-removal-service/573-home-removal-service-price-comparison) |
| Global moving-company software market size, 2025 | **US$1.5–2.5B**, ~10% CAGR (estimates vary by report scope — the lower end is dedicated moving software; the wide range is a broader logistics/fleet-management categorization) | [market.us](https://market.us/report/moving-company-software-market/), [Verified Market Research](https://www.verifiedmarketresearch.com/product/moving-company-software-market/) |

**Not found in public sources** (searched, not located): total number of registered removal companies operating in Hong Kong, and annual volume of stamped tenancy agreements (which would give a harder floor for moves/year than property sales alone). Both are flagged as open research items below rather than estimated.

## 2. Derived figures (calculated from the sourced rows above — not independently published)

These are arithmetic on the sourced inputs, shown so the assumption is visible and replaceable:

- **Consumer removals spend, HK, per year:** if total household moves/year is estimated in the 150k–250k range (see caveat below) at the Consumer Council's average HK$8,627/move, implied annual spend is **~HK$1.3–2.2B**. This multiplies a sourced average price by an *unsourced* volume estimate — treat the resulting range as illustrative, not a citable figure.
- **HK software SAM, benchmarked against HomeSurvey.ai's US$20/survey (~HK$156) pay-as-you-go price:** at HK$100–150/survey against the same 150k–250k moves/year range, **~HK$15–37M/year**. Same caveat — depends on an unsourced volume estimate.

**Caveat on the 150k–250k moves/year figure used above:** this number is *not* independently sourced. It was reasoned from the 69,135 sourced property-sale transactions (a hard floor, since not every sale produces a move and rentals aren't counted) plus an assumed 6–9% annual household mobility rate applied to the 2.78M sourced household count. Both inputs are sourced; the mobility-rate assumption and the resulting range are not. Do not present this as a cited figure on a slide — present it as a stated assumption, or replace it if a real HK mobility-rate or tenancy-volume statistic turns up.

## 3. Competitive landscape (sourced)

| Company | Segment | Sourced facts |
|---|---|---|
| **GoGoX Moving** | HK adjacent platform | Prices from a customer-supplied inventory list; HK$500+ for ≤15 boxes, HK$1,000+ for a scheduled move; surcharges for stairs and parking beyond 50m. — [GoGoX Moving](https://www.gogox.com/moving/) |
| **Lalamove** | HK adjacent platform | Moving add-on from HK$78, +HK$200 for door-to-door; fare floats on traffic/demand/tolls. — [Lalamove HK Moving Help](https://www.lalamove.com/en-hk/help-move) |
| **Yembo** | Global AI-survey incumbent | AI video self-surveys + 3D property reconstruction. Case studies: New World Van Lines cut outsourced pre-move surveys >85%, total survey time −42%; California Moving Systems +35% survey volume, survey time halved; reps reportedly quote 3× more customers. Total funding **US$12.9M**, an **US$8.5M Series A in April 2021** led by Imagen Capital Partners — no later round found. — [Yembo AI Surveys](https://yembo.ai/moving/ai-surveys), [Yembo Series A press release](https://www.prnewswire.com/news-releases/yembo-secures-8-5-million-series-a-financing-round-led-by-imagen-capital-partners-301273080.html); revenue estimate (~US$3.4M ARR, third-party estimate, not company-disclosed) — [Latka](https://getlatka.com/companies/yembo) |
| **HomeSurvey.ai** | Global AI-survey challenger | US$20/survey, pay-as-you-go, no subscription/minimums/setup fee; claims 93% accuracy before human review, 2,000+ item types; "move-day audit" with ~US$750 average recovery. — [HomeSurvey.ai vs Yembo comparison](https://homesurvey.ai/compare/homesurvey-vs-yembo/) |
| **SmartMoving / MoveitPro / Movegistics** | Moving-company CRM layer | SmartMoving and MoveitPro have no native AI survey and integrate Yembo or ComeHome.ai as a separate subscription; Movegistics bundles its own AI survey natively. — [Capterra: Yembo alternatives](https://www.capterra.com/p/207507/Yembo/alternatives/) |

## 4. Open research items — Hong Kong (not yet sourced)

- Total count of registered/operating removal companies in Hong Kong.
- HK annual tenancy-agreement volume (IRD does not publish this; Rating and Valuation Department may).
- A directly-published HK "moves per year" figure, to replace the derived range in §2.

---

## 5. Regional comparison — Asia-Pacific

Grades reflect source quality, not figure size: **A** = government statistics
office or audited company filing; **B** = official registry with a known
coverage limitation; **C** = industry blog or trade press, unverified against a
statistics office; **D** = market-report estimate that failed cross-checking.

| Market | Households | Moves/year | Avg move cost | Industry size | Operators | Grade |
|---|---|---|---|---|---|---|
| **Hong Kong** | 2.78M | ~150–250k (Derived, §2) | **HK$8,627** avg (~US$1,100) | ~HK$1.3–2.2B (Derived) | 20 surveyed | **A** on price, Derived on volume |
| **Mainland China** | — | **~40M households**, ~70% urban | — | ¥186–200B claimed vs. ¥6B platform segment (30× spread — see §6) | **120,000+** | **A** on volume, **D** on size |
| **Japan** | — | **5,190,548 inter-municipal movers** (2025) | — | **~¥400B** (~US$2.7B) | — | **A** |
| **South Korea** | — | **6,283,000 movers** (2024); ~2,094,333 jobs | **₩1.1M** (~US$800), 5-tonne packing move | **≥₩3 trillion** (~US$2.2B) | ~3,000 | **C** |
| **Singapore** | **1,487,100** (2025) | — (not published) | **S$300–3,500** typical | — (not published) | — | **A** on households, **C** on price |
| **Taiwan** | — | — | — | — | **203 registered** | **B** |

Currency conversions above are approximate and **Derived** (¥150/US$, ₩1,380/US$, HK$7.8/US$); the sourced figure is always the local-currency one.

## 6. Per-market detail

### Japan — the highest-quality data in the region

**5,190,548 people moved between municipalities in calendar 2025**, down 17,198 (−0.3%) year-on-year and the third consecutive annual decline; **2,515,731** of those crossed prefectural boundaries. This is a census-grade administrative count from resident-registration records, not a survey estimate. **Grade A.** — [総務省統計局, 住民基本台帳人口移動報告 2025年結果 (Feb 2026)](https://www.stat.go.jp/data/idou/2025np/jissu/pdf/2025gaiyou.pdf), [press release](https://www.soumu.go.jp/menu_news/s-news/01toukei03_01000138.html)

Market size **~¥400B** (~US$2.7B) — **not** the ¥1 trillion figure often repeated in trade press. **Grade C** (industry source), but it cross-checks against audited company revenue: **Sakai Moving Center ¥121.023B** (FY ending Mar 2025) and **Art Moving Center ¥88.6B** (FY ending Sep 2024) — two firms alone exceed half the stated market, which puts ¥400B in a plausible order of magnitude. — [アップル引越センター market-size analysis](https://www.apple-hikkoshi.co.jp/archives/390), [top-3 company analysis](https://www.apple-hikkoshi.co.jp/archives/8725)

Per-firm job volumes for sanity-checking unit economics: Sakai handled ~672,000 moves and Nippon Express ~468,000 in FY2013. **Grade C.** — [引越しラクっとNAVI](https://hikkoshi-rakunavi.com/wp/?manual=214)

**Seasonality — relevant to the product thesis.** March move volume runs roughly **2× a normal month**, to the point that MLIT runs an annual public campaign asking households to spread moves outside the peak. **Grade A** (ministry publication). — [国土交通省自動車局貨物課](https://www.mlit.go.jp/report/press/content/001448869.pdf), [全日本トラック協会](https://jta.or.jp/member/hikkoshi_member.html)

This matters for MoveAI's pitch: if demand is 2× concentrated in a six-week window, the industry's binding constraint is surveyor headcount it cannot economically hire for that window. Automated surveying sells as elastic capacity at peak, not merely as a cost saving.

### Mainland China — volume is real, market-size figures are not trustworthy

**~40 million households move annually, ~70% of them urban. Grade A-equivalent for planning purposes** (widely repeated across independent industry reports, though the underlying survey is not named). — [报告大厅 industry analysis](https://m.chinabgao.com/freereport/97868.html)

**120,000+ moving companies** as of 2023. — [报告大厅 2025–2030 industry report](https://www.chinabgao.com/report/16608097.html)

**Market size is unusable as cited. Grade D.** Figures found across sources: ¥6B (2021), ¥186B (2024), ¥200B (2025 forecast) — a 30× spread. The only reconcilable reading is that **¥6B describes the internet-platform-mediated segment** (growing ~30%/year) while ¥186–200B claims the entire fragmented industry including informal operators. Do not present either without stating which scope it covers. — [报告大厅 2023 analysis](https://m.chinabgao.com/info/1245712.html), [报告大厅 2024 analysis](https://m.chinabgao.com/freereport/97868.html)

**The trustworthy China numbers come from Huolala's (货拉拉) HKEX prospectus. Grade A** (filed financials):

- 2024 revenue **US$1.593B**, +19.39% YoY — [新浪财经](https://finance.sina.com.cn/roll/2025-04-03/doc-inerxarq5448626.shtml)
- 2024 global GMV **US$11.137B**, +18.3%; **779 million** completed orders — [每日经济新闻](https://www.nbd.com.cn/articles/2025-04-04/3819382.html)
- Moving vertical (as of Sep 2024): professional moving service in **64 cities**, driver-assisted moving in **363 cities**, **40M+ cumulative moving customers**, **50,000+** monthly-active moving workers, **100,000+** enterprise clients — [新浪财经](https://finance.sina.com.cn/jjxw/2024-11-16/doc-incwfiet9346018.shtml)
- Peak-season concentration mirrors Japan's: **+104% YoY order volume** during the Mar 11–31 2024 moving season — [同上](https://finance.sina.com.cn/jjxw/2024-11-16/doc-incwfiet9346018.shtml)

**Structural read:** Huolala and Kuaigou Dache (快狗打车) are consolidating a 120,000-operator long tail that is losing on operating cost and service capability. A measurement layer is how a long-tail operator competes on quote credibility rather than price — but the platforms are simultaneously the most likely acquirer and the most likely fast-follower.

### South Korea — best price-point data, weakest sourcing

**6,283,000 people moved in 2024**; approximately **2,094,333 moving jobs**; average **₩1.1M** (~US$800) for a 5-tonne packing move (포장이사); market **≥₩3 trillion** (~US$2.2B) once ladder-truck, cleaning and installation add-ons are counted; approximately **3,000 operators**. **Grade C** — traced to an industry blog, not a statistics office. — [이삿짐닷컴](https://www.24jim.com/415)

Corroborating older figure: 포장이사 estimated at **₩2.7 trillion** in 2017 by an accounting-trade column, which makes ₩3T+ in 2024 directionally plausible. **Grade C.** — [CLO](http://clomag.co.kr/article/1817)

**Before citing any Korean figure live, verify against [KOSIS](https://kosis.kr/) 국내인구이동통계**, which is the authoritative equivalent of Japan's 移動報告 and would upgrade the mover count to Grade A.

### Singapore — small, high-value, easiest second market

| Figure | Value | Grade | Source |
|---|---|---|---|
| Resident households | **1,487,100** (2025), +1.6% YoY from 1,463,400 | **A** | [SingStat via Statista](https://www.statista.com/statistics/728350/number-of-households-singapore/) |
| Average household size | **3.06 persons**; **77.2%** of resident households in HDB flats | **A** | [SingStat / smartwealth.sg compilation](https://smartwealth.sg/housing-household-statistics-singapore/) |
| HDB resale transactions | **26,169** (2025), −9.7% from **28,986** (2024) — a five-year low | **A** | [EdgeProp Singapore](https://www.edgeprop.sg/property-news/hdb-resale-prices-plateaued-4q2025-transactions-sink-five-year-low) |
| Typical local move cost | **S$300–3,500** depending on property size and scope (S$180–6,000+ at the extremes) | **C** | [Jean Movers](https://jeanmovers.com.sg/cost-to-move-in-singapore/), [Homejourney](https://www.homejourney.sg/blog/moving-service-price-singapore-2026-full-cost-breakdown-202602212001) |

**Not published:** aggregate moving-industry revenue, operator count, or annual moves. Build these from [HDB Key Statistics 2024/2025](https://www.hdb.gov.sg/-/media/hdb-pulse/reports/annual-reports-and-financial-statements/HDB_Key-Statistics-2025.pdf) and [SingStat's Resident Households By Tenancy dataset](https://data.gov.sg/datasets/d_0af1b3f4fe472349704e4e2576687a8a/view).

**Why Singapore is the natural second market:** highest price-per-move in the region outside Japan, English-language, and a high-rise/lift-access building stock nearly identical to Hong Kong's — so the access-factor model in `pricing.py` transfers with minimal recalibration. GoGoX already runs a moving service there ([GoGoX Singapore](https://www.gogox.com/sg/moving/)), so a Hong Kong partner integration ports directly.

### Taiwan — thinnest data of the six

**203 approved moving companies** on the MOEA Department of Commerce business registry. **Grade B** — treat as a floor, since it likely counts only firms registered under a moving-specific business classification. — [Zstats compilation of 經濟部商業司 registry data](https://zstats.click/moving/)

Industry characterization: predominantly sub-scale operators — "three or four trucks and five or six workers" is described as sufficient for normal business — in a competitive market with modest demand. **Grade C.** — [台灣光華雜誌](https://www.taiwan-panorama.com/Articles/Details?Guid=b9424152-a640-45c3-a923-253e38145f00)

Pricing benchmarks: [PRO360達人網 2026 price table](https://www.pro360.com.tw/price/moving).

### Global backdrop

| Figure | Value | Grade | Source |
|---|---|---|---|
| Global moving-services market | **US$110.97B (2025) → US$143.18B (2030)**, 5.23% CAGR (Mordor Intelligence) | **C** | [市場調査レポート](https://www.marketresearch.co.jp/insights/moving-services-market-mordor/) |
| Global moving-company software | **US$1.5–2.5B (2025)**, ~10% CAGR | **C** | [market.us](https://market.us/report/moving-company-software-market/) |

## 7. Derived — regional addressable market

**All figures in this section are Derived.** The arithmetic is shown so each
assumption can be replaced. The price point is benchmarked, not invented:
HomeSurvey.ai charges **US$20/survey** pay-as-you-go (§3), so US$15/survey is a
deliberate undercut of a published competitor price, and US$8 for mainland
China reflects that market's lower price-per-move.

| Market | Addressable moves/year | Basis | @ US$15/survey |
|---|---|---|---|
| Hong Kong | ~200k | Midpoint of the §2 derived range | **US$3M** |
| Singapore | ~120k | See assumption note below | **US$1.8M** |
| South Korea | 2.09M | Sourced job count (§6, Grade C) | **US$31M** |
| Japan | ~3M | See assumption note below | **US$45M** |
| Mainland China | ~28M | 40M households × 70% urban (both sourced) | **US$224M** at US$8 |
| **Regional total** | | | **~US$300M/year** |

**Assumptions that are not sourced, stated explicitly:**

- **Japan ~3M household moves** is converted from the sourced 5,190,548 *persons* moving between municipalities. Persons ≠ households, and the official figure **excludes intra-municipal moves**, which are substantial and would push the number up. Roughly 5.19M ÷ ~2.2 persons per moving household ≈ 2.4M inter-municipal household moves, rounded to ~3M to partially account for the excluded intra-municipal volume. This is the weakest link in the table — replace it if a published 引越し件数 total surfaces.
- **Singapore ~120k moves** is inferred from 1.487M households at a mobility rate comparable to Hong Kong's assumed 6–9%, cross-checked against 26,169 HDB resale transactions as a floor. Not sourced.
- **South Korea's 2.09M** inherits the Grade C sourcing of §6 and should be re-derived from KOSIS.

**How to present this.** Hong Kong alone is a ~US$3M SAM — state that plainly rather than inflating it, because the expansion path is the actual argument: HK → Singapore → Japan/Korea → mainland China is a **~US$300M/year opportunity assembled from government statistics and filed company financials**, with a coherent sequencing logic (start in the densest, highest-rise, hardest-to-measure market, where US-built incumbents fit worst, then expand into markets with comparable building stock).

## 8. Source-quality warning and citation rule

This sector's market-report estimates fail basic sanity checks. Two documented
examples encountered while compiling this file:

- One research vendor put **Japan's moving-services market at "USD 3,028.82 billion" for 2025** — approximately 60× Japan's entire GDP, and ~27× the same page's own global moving-services figure. — [deepmarketinsights](https://deepmarketinsights.com/ja/vista/insights/moving-services-market/japan)
- Global moving-company software was variously reported at **US$1.53B, US$1.8B, US$2.5B, and US$16.03B** for the same year, a >10× spread. — see §1 sources plus [Verified Market Reports](https://www.verifiedmarketreports.com/product/moving-company-software-market/)

**Citation rule for the live pitch — cite only these classes of source:**

1. **Government statistics offices** — 総務省統計局 (Japan), C&SD (HK), Land Registry (HK), SingStat / HDB (Singapore), KOSIS (Korea), 經濟部商業司 (Taiwan), 国土交通省 (Japan).
2. **Consumer/market regulators** — HK Consumer Council.
3. **Filed or audited company financials** — Huolala's HKEX prospectus, Sakai and Art annual results, Yembo's funding announcements.

Anything Grade C or D belongs in the appendix with its grade attached, or not
on the slide at all. Every A-grade figure in this document survives a judge
checking it on a phone during the Q&A; the C and D figures may not.

## 9. Open research items — regional

- **South Korea:** confirm the 2024 mover count and job count against KOSIS 국내인구이동통계; upgrade §6 from Grade C to Grade A.
- **Japan:** find a published total 引越し件数 (including intra-municipal moves) to replace the derived ~3M household-move figure in §7.
- **Singapore:** operator count and industry revenue — build from HDB Key Statistics and SingStat tenancy data.
- **Mainland China:** locate a first-party market-size figure (iResearch/艾瑞 or equivalent) with a stated scope, to resolve the ¥6B-vs-¥186B ambiguity in §6.
- **Taiwan:** annual internal-migration volume from 內政部戶政司, to pair with the 203-operator registry count.
- **All markets:** whether Yembo, HomeSurvey.ai or ComeHome.ai have any Asia-Pacific presence or localized product — not found in this pass, and a negative finding here is itself a positioning asset.

---

*Compiled 2026-08-05, regional sections added 2026-08-06, via web search. Figures reflect what was publicly findable at that time; re-verify before using in a live pitch, especially funding/revenue figures and market-size estimates, which change quickly and — per §8 — are frequently wrong at source.*
