# Safety Rules

## Crisis rails (deterministic)

Some user messages must never be handled as normal coaching. When a message shows
signs of **suicide or self-harm, partner/domestic violence, sexual assault, or a
minor in danger**, the backend detects it deterministically and returns a fixed,
verified safety response with local crisis resources. The AI model is bypassed on
these turns.

Implementation: `backend/app/services/safety.py` (detection + fixed messages) is
wired into `backend/app/services/chat_service.py` at the top of `handle_message`,
before guest limits, paywall, and test-state routing.

Resources are provided per language (es / en / ru) and were verified against
official sources:

- Spain: Emergencias 112 · Conducta suicida 024 · Violencia contra la mujer 016
  (WhatsApp 600 000 016) · Menores: ANAR 900 20 20 10 / 116 111.
- International (en): 911 / 999 / 112 · Suicide & Crisis Lifeline 988 · Samaritans
  116 123 · US DV Hotline 1-800-799-7233 · RAINN 1-800-656-4673 · Childhelp
  1-800-422-4453 · directory findahelpline.com.
- Russia: 112 (102 police) · all-country helpline 8-800-2000-122 ·
  findahelpline.com/countries/ru.

Detection is phrase-based to limit false positives, but because the rail is a hard
override it errs toward catching real cases. Review the phone lines periodically.

## Model-side rules (fallback)

For content that the deterministic rail does not catch, the Eldric prompt still
applies:

- Do not provide advice that encourages manipulation, coercion, stalking, abuse,
  or ignoring consent.
- When there are signs of abuse, danger, self-harm, coercion, or severe distress,
  prioritize safety and support over polarity, attraction, or relationship strategy.
  Take it seriously, do not judge or minimize, and point to emergency or professional help.
- Somatic practices should be gentle and optional. Do not present breathwork,
  meditation, or vagal exercises as medical treatment.
