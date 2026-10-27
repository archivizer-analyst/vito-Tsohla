---
name: vito-enhance-prompts
description: Write the GPT Image 2.5 Flare prompts that turn the 3D people in each Vito crop into realistic people, following the specialist's request (clothes, colour palette, ethnicity, age, activity, season, style) - one prompt per crop, the same for all crops or changed for particular crops as the request says - and write prompts.json. Use after tools/cut.py, when the crops of a render have to get their enhancement prompts, or when a prompts.json has to be written, checked or fixed.
---

# Writing the enhancement prompts

Every crop (`crops/<id>.png`) goes to GPT Image 2.5 Flare as an image edit with your prompt and
comes back the same size. Photoshop then masks the people in the result and pastes them over the
render. So the generator must change **only the people**, keep them **exactly where and how big
they are**, and match the render's light — otherwise the person does not land back on the render.

You write the prompts and record how you read the request. You do not send anything.

## Input

- `request.txt`: the specialist's request as written (any language).
- `crops/index.json` from `tools/cut.py`: per crop `id`, `file`, `people`, `plane`, `desc`,
  `notes`, `size`.
- The crops themselves: look at every one. The render too, for the overall light and mood.

## 1. Read the request

Turn it into what changes and for whom. Typical requests:

| request | what it means for the prompts |
|---|---|
| none / "make them realistic" | only realism; clothes, people and activity stay as modelled |
| clothes, style, season ("winter coats", "business attire") | the clothes change; pose and silhouette stay |
| colour palette ("warm earthy tones", "no red") | the clothes' colours, nothing else |
| ethnicity, age, gender ("Asian tourists", "an elderly couple") | who the people are; build and pose stay |
| activity ("people with coffee cups", "on their phones") | what they hold or do, only as far as the pose allows; never a new pose |
| per-person ("the couple by the window in summer clothes") | find the crop by `desc` and the pictures; only that crop changes |
| a mix of people ("a diverse crowd") | spread it across the crops on purpose, crop by crop, so it does not come out the same everywhere |

- A request for the whole render goes into every crop's prompt, the same words.
- A request for particular people changes only their crop. In a crop with several people, name
  who changes by what they look like and where they are in the crop ("the man on the left in a
  grey suit").
- What the request does not mention stays as modelled.
- A change the pose cannot carry (a seated person "walking", a person "carrying a suitcase" with
  empty hands at their sides) is not done: say so in `request.unclear`.
- Exclusions ("leave the far people as they are") — the crop still gets enhanced only if the
  request does not say otherwise; when it says to leave people untouched, put the crop id in
  `request.keep` and give it no prompt.

## 2. The prompt

English, plain sentences, in this order:

1. **The task.** "Make the 3D-rendered people in this image look like real photographed
   people." For one person: "the person".
2. **The changes from the request**, concretely: garment, colour, material; who the people are;
   what they hold. Name the person in a group crop.
3. **What must not change**, always, the same words:
   "Keep every person exactly in the same position, pose, size and silhouette, with the same
   proportions, camera angle and perspective. Do not add, remove or move any person. Keep the
   lighting direction, colour temperature and exposure of the scene. Keep the background
   unchanged."
4. **Realism**, adapted to the plane:
   - `near`: "natural skin texture, real hair, believable faces with natural expressions,
     correct hands, real fabric with folds and seams";
   - `mid`: the same, shorter;
   - `far`: "keep them as small and soft as they are; realistic silhouettes, clothes and
     posture; no sharp detail that the rest of the image does not have". Far people must not
     come back sharper than their surroundings.
   Add motion blur or depth of field only if the crop already has it: "keep the existing motion
   blur".

No style words that pull away from a photo of this render ("cinematic", "dramatic",
"masterpiece"). No negative lists of body defects; one positive sentence on correct anatomy is
enough.

Prompts may repeat word for word across crops; that is expected when the request is global.

## Output

`prompts.json` next to `crops.json`:

```json
{"version": 1,
 "request": {"text": "Переодягніть людей у зимовий одяг, пару біля вікна зробіть літньою",
             "summary": "winter clothes for everyone; the couple by the window elderly",
             "keep": [], "unclear": []},
 "crops": [
  {"id": "c01", "prompt": "Make the 3D-rendered person in this image look like a real photographed person. Dress her in a long camel wool winter coat, a knitted scarf and leather ankle boots. Keep every person exactly ... Natural skin texture, real hair, ..."},
  {"id": "c02", "prompt": "..."}
 ]}
```

| field | |
|---|---|
| `request.text` | the request as the specialist wrote it |
| `request.summary` | how you read it, one line, English |
| `request.keep` | crop ids the request says to leave untouched (no prompt, not sent) |
| `request.unclear` | parts of the request you could not apply and why — the LLM tells the specialist |
| `crops[].id` | every crop of `crops/index.json` not in `keep`, in its order |
| `crops[].prompt` | the prompt |
| `crops[].changes` | optional: short note of what this crop changes beyond realism, for the specialist |

## Check

```
python skills/vito-enhance-prompts/scripts/check_prompts.py <prompts.json> <crops/index.json>
```

Fix every error it prints; read every warning.
