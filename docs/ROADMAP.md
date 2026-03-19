# Broker / Lead app – roadmap

Planned features and implementation notes.

---

## Suggested implementation order

1. **Mark as sold** – smallest change; unblocks “sold” in UI and in cron logic.
2. **Scheduling visits** – core to closing deals; define visit model and states once, then add UI.
3. **24h cron** – once visits and “interested” exist, cron can suggest “schedule a visit?” or “still looking?” by state.
4. **Reviews** – after sold or visit completed, prompt for review; keeps the flow logical.

---

## 1. Scheduling property visit

- Lead (or broker) can request/schedule a visit for a recommended property.
- **Visit states**: Model with clear statuses, e.g. `requested` → `confirmed` / `cancelled` / `completed`, so both sides see the same state (reuse or extend existing state-machine pattern).
- Likely needs: visit model (lead_id, property_id, preferred_slots, status, requested_at, confirmed_at), UI in Lead Chat and Broker Dashboard to create/view/confirm, optional calendar or slot picker.

---

## 2. Finalising property → marking as sold

- When a lead finalises a property (or broker closes the deal), mark the property as sold and optionally link to the lead/deal.
- **Audit**: Store who marked it sold and when (and which lead); helps with disputes and analytics.
- Likely needs: property status transition (`AVAILABLE` → `SOLD`), optional deal/closure model (lead_id, property_id, closed_at, closed_by), broker UI to mark sold (or trigger from lead action).

---

## 3. Cron job (every 24 hrs) by user state

- Scheduled job runs every 24 hours; based on each lead’s state, send follow-up messages or prompts (e.g. “Would you like to schedule a visit?”, “Any questions about the recommended properties?”).
- **Idempotent**: Track “last follow-up sent at” (or last run) per lead so duplicate runs don’t send twice; same for “already asked for review”.
- **“Interested” signal**: Use existing `PropertyRecommendation.interested` in lead UI (“I’m interested” / “Not for me”); broker sees signal and cron can tailor (“You showed interest in X – want to schedule a visit?”).
- Likely needs: scheduler (APScheduler in-process first; Celery Beat or system cron if you need scale), state-aware logic per lead, way to send messages (Kafka/API) without normal chat flow.

---

## 4. Review by lead to broker

- After a deal or interaction, the lead can leave a review/rating for the broker.
- **When to ask**: e.g. after property marked sold or visit completed; avoid asking repeatedly (track “review requested at” / “review submitted”).
- Likely needs: review model (lead_id, broker_id, rating, text, created_at), API to submit and fetch reviews, Lead app UI to submit, Broker app UI to display.

---

## Other suggestions

- **Broker identity**: Properties use `broker_id` (FK to `leads.id`). If brokers become a separate role later, consider a dedicated `brokers` (or user-role) model so “review by broker” and “mark as sold” are clearly tied to the right entity.
- **Quick win**: “Need help?” / “Request callback” in lead UI that creates a task or notification for the broker, so re-engagement isn’t only via the 24h cron.

---

*When you’re ready to implement any item, we can break it into tasks and wire it into the existing consumer, producer, and UI.*
