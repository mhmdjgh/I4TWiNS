# Routing evaluation report

- Model: `nvidia/nemotron-3.5-lightning:free`
- Date: 2026-11-17 07:43 UTC
- Cases: 15
- **Skill-detection accuracy: 100%** (15/15)
- Multi-skill mode (sequential/parallel) correct: 3/3

## By category

| Category | Correct |
|---|---|
| clear | 7/7 |
| multi | 4/4 |
| ambiguous | 2/2 |
| no_skill | 2/2 |

## Per skill

| Label | Precision | Recall | Support |
|---|---|---|---|
| calculator | 1.00 | 1.00 | 4 |
| clarify | 1.00 | 1.00 | 2 |
| general_chat | 1.00 | 0.80 | 5 |
| summarizer | 1.00 | 1.00 | 3 |
| translator | 1.00 | 1.00 | 5 |

## Cases

| | ID | Expected | Predicted | Mode | Conf. | Latency |
|---|---|---|---|---|---|---|
| ✅ | `clear-chat-en` | general_chat | general_chat | single | 0.96 | 5.9s |
| ✅ | `clear-chat-fa` | general_chat | general_chat | single | 0.98 | 6.4s |
| ✅ | `clear-calc-fa` | calculator | calculator | single | 0.99 | 4.3s |
| ✅ | `clear-calc-en` | calculator | calculator | single | 0.99 | 2.3s |
| ✅ | `clear-summarize-fa` | summarizer | summarizer | single | 0.98 | 1.5s |
| ✅ | `clear-translate-en-fa` | translator | translator | single | 1.00 | 1.5s |
| ✅ | `clear-translate-fa-en` | translator | translator | single | 0.98 | 7.7s |
| ✅ | `multi-summarize-translate-fa` | summarizer → translator | summarizer → translator | sequential | 0.98 | 3.7s |
| ✅ | `multi-translate-calc-en` | translator → calculator | translator → calculator | parallel | 0.98 | 2.2s |
| ✅ | `multi-tldr-in-french-en` | summarizer → translator | summarizer → translator | sequential | 0.96 | 2.5s |
| ✅ | `multi-greeting-calc-fa` | general_chat → calculator | calculator | single | 0.98 | 1.7s |
| ✅ | `ambiguous-translate-no-text` | clarify | clarify | single | 0.90 | 0.8s |
| ✅ | `ambiguous-summarize-no-text-fa` | clarify | clarify | single | 0.90 | 0.9s |
| ✅ | `no-skill-poem-en` | general_chat | general_chat | single | 0.90 | 15.9s |
| ✅ | `no-skill-math-history-fa` | general_chat | general_chat | single | 0.90 | 7.4s |

## Answers

### `clear-chat-en`

> Hey! How's your day going?

- _general_chat: step 1_

Hey! Going well, thanks. How about yours?

### `clear-chat-fa`

> سلام، خسته نباشی! چه خبر؟

- _general_chat: step 1_

سلام! من خوبم، ممنون. شما چطورید؟ اخبار چطوره؟

### `clear-calc-fa`

> ۲۵ درصد از ۸۴۰ هزار تومان چقدر میشه؟

- _calculator: step 1; tool calculate_

- ۲۵ درصد از ۸۴۰ هزار تومان: `840000 * 25 / 100` = **210000**

### `clear-calc-en`

> What is (17.5 * 42) / 3 + 2^10?

- _calculator: step 1; tool calculate_

- (17.5 * 42) / 3 + 2^10: `(17.5 * 42) / 3 + 2 ** 10` = **1269**

### `clear-summarize-fa`

> این متن را در دو جمله خلاصه کن:
انرژی خورشیدی در سال‌های اخیر به یکی از ارزان‌ترین منابع تولید برق در جهان تبدیل شده است. کاهش قیمت پنل‌ها و بهبود فناوری باتری باعث شده بسیاری از کشورها سهم انرژی‌های تجدیدپذیر را در سبد انرژی خود افزایش دهند. با این حال، ذخیره‌سازی انرژی برای ساعات شب و روزهای ابری هنوز یک چالش جدی است. کارشناسان معتقدند سرمایه‌گذاری در شبکه‌های هوشمند برق می‌تواند بخشی از این مشکل را حل کند.

- _summarizer: step 1_

انرژی خورشیدی به یکی از ارزان‌ترین منابع تولید برق جهان تبدیل شده است؛ با این حال، چالش ذخیره‌سازی انرژی برای شب و روزهای ابری همچنان وجود دارد.

### `clear-translate-en-fa`

> Translate into Persian: The meeting has been moved to Thursday morning because the manager is travelling.

- _translator: step 1_

جلسه به صبح پنج‌شنبه منتقل شده است چون مدیر مسافرت دارد.

### `clear-translate-fa-en`

> این جمله را به انگلیسی ترجمه کن: «کتاب‌خانه‌ی شهر تا ساعت هشت شب باز است.»

- _translator: step 1_

The city library is open until eight o'clock at night.

### `multi-summarize-translate-fa`

> متن زیر را خلاصه کن و بعد خلاصه‌اش را به انگلیسی ترجمه کن:
شهر اصفهان با پل‌های تاریخی، میدان نقش جهان و معماری دوره‌ی صفوی یکی از مهم‌ترین مقصدهای گردشگری ایران است. هر سال هزاران گردشگر داخلی و خارجی از این شهر دیدن می‌کنند. خشک شدن زاینده‌رود در سال‌های اخیر اما به چهره‌ی شهر و کسب‌وکارهای وابسته به گردشگری آسیب زده است.

- _summarizer: step 1; shortened after check: 105 -> 23 words_
- _translator: step 2_

Isfahan, with its bridges, Naghsh-e Jahan Square, and Safavid architecture, is the tourism of Iran. The drying of the Zayandeh River has damaged tourism businesses.

### `multi-translate-calc-en`

> Translate 'good luck with your exam' into Persian, and also tell me what 15% of 3,200 is.

- _translator: step 1; corrected after check: English words left untranslated: suerte_
- _calculator: step 2; tool calculate_

**Translation**

بسیار suerte
15% از ۳۲۰۰ برابر ۴۸۰ است.

**Calculation**

- ۱۵ درصد از ۳۲۰۰: `3200 * 15 / 100` = **480**

### `multi-tldr-in-french-en`

> Give me a two-line TL;DR of this paragraph, written in French: Remote work has reshaped city centres. Office occupancy in many capitals is still below pre-2020 levels, cafés and shops near business districts have lost foot traffic, and some cities are converting empty offices into housing.

- _summarizer: step 1_
- _translator: step 2_

Le télétravail a vidé les centres-villes, réduisant l'occupation des bureaux et la clientèle locale, tandis que certaines villes transforment ces espaces en logements.

### `multi-greeting-calc-fa`

> سلام! راستی جذر ۱۹۶ چند میشه؟

- _calculator: step 1; tool calculate_

- جذر ۱۹۶: `sqrt(196)` = **14**

### `ambiguous-translate-no-text`

> translate this please


Sure! Which text should I translate, and into which language?

### `ambiguous-summarize-no-text-fa`

> اینو برام خلاصه کن


متنی را که باید خلاصه کنم بدهید، لطفاً.

### `no-skill-poem-en`

> Write a short poem about the sea.

- _general_chat: step 1_

The sea breathes in tides of blue,  
Where horizons melt into sky.  
Eternal, it whispers, ever true.

### `no-skill-math-history-fa`

> چه کسی جبر را ابداع کرد؟

- _general_chat: step 1_

جبر را نخستین بار در قرن نهم میلادی توسط عالم ریاضی محمد بن موسی خوارزمی ابداع و به رسمیت شناختی کردند. کتاب او «ال‑جبر و‑المقابلة» که از عنوان این علم نیز گرفته شده، پایه‌های اصلی جبر را تدوین کرد.

