# Vito

Оживляє 3D-людей на рендері (*vita* — життя). Спеціаліст кладе рендер у задачу на archivizer.com
і пише запит у чат («зробити людей реалістичнішими», «переодягнути в зимовий одяг», «бізнес-стиль
у лобі»). LLM платформи знаходить людей, ріже кропи, пише під кожен кроп промпт, сервер Vito
енхенсить кропи в GPT Image 2.5 Flare, а Photoshop на сервері збирає `.psd`: кожен покращений
кроп — окремий смарт-об'єкт у повній роздільності з маскою людини поверх рендера.

Як Placido і CAD2Max: агент на archivizer.com, LLM лише там, де без неї не обійтися (знайти людей,
зрозуміти запит, написати промпти), решта — скрипти.

## Кроки

| # | Крок | Хто | Вихід | Код / скіл |
|---|---|---|---|---|
| 1 | Рендер + запит у чаті | спеціаліст | `render.*`, `request.txt` | — |
| 2 | Знайти людей, рамки кропів | віжн-LLM | `crops.json` | скіл [vito-people-crops](skills/vito-people-crops/SKILL.md) |
| 3 | Нарізати кропи | Python | `crops/NN.png`, `crops/index.json` | `tools/cut.py` |
| 4 | Промпти під запит | LLM | `prompts.json` | скіл [vito-enhance-prompts](skills/vito-enhance-prompts/SKILL.md) |
| 5 | Енхенс | GPT Image 2.5 Flare (Image API, edits) | `enhanced/NN.png` | `tools/enhance.py` |
| 6 | Маски і збірка | Photoshop на сервері | `result.psd`, `result.jpg` | `tools/assemble.py` + `tools/assemble.jsx` |

Окремого етапу перевірки немає: енхенсяться всі кропи в кожному запуску, у цьому і сенс.
Маски робить Photoshop (Select Subject на шарі покращеного кропа), а не маски з 3ds Max: ті не
збігаються з покращеними людьми.

## Папка запуску

```
job/
  render.jpg            рендер спеціаліста (будь-яке ім'я; шлях — у crops.json)
  request.txt           запит спеціаліста як є
  crops.json            крок 2: рамки кропів
  crops/                крок 3: c01.png ... + index.json (рамка на рендері, розмір для генератора)
  prompts.json          крок 4: промпт на кожен кроп
  enhanced/             крок 5: c01.png ... (розмір як у crops/)
  result.psd            крок 6: рендер + шар з маскою на кожен кроп
  result.jpg            крок 6: те саме пласким зображенням
```

## Команди

```
python skills/vito-people-crops/scripts/grid.py job/render.jpg job/_grid.jpg
python skills/vito-people-crops/scripts/check_crops.py job/crops.json
python tools/cut.py job/crops.json
python skills/vito-enhance-prompts/scripts/check_prompts.py job/prompts.json job/crops/index.json
python tools/enhance.py job            # OPENAI_API_KEY; --dry-run показує запити без відправки
python tools/assemble.py job           # Photoshop через COM (Windows), без вікна, лишається відкритим; шари в групі people_enhanced
```

Залежності: Python 3.10+, Pillow, requests; Photoshop 2025 на машині збірки.

## Відкриті питання

- Чи тримає Flare позу/світло/масштаб достатньо, щоб кроп ліг назад без зсуву.
- Select Subject на кропі з кількома людьми і меблями: чи бере лише людей.
- Старий силует: якщо покращена людина вужча за 3D-людину, краї старої видно поза маскою.
- Тіні людей: лишаються з рендера.
