# PM Notebook

> Running journal — PM frameworks grounded in real observations from this project.

---

## PM Fundamentals

**Discovery vs. Delivery**
The gap between understanding what to build (discovery) and building it (delivery). Engineers are trained for delivery; PM skill is in discovery.

**Outcome vs. Output**
Output: a feature shipped. Outcome: a behavior that changed. Ship outcomes, not features.

**The "so what" test**
For any feature idea: "So what?" Keep asking until you reach a user behavior or business result. If you can't get there, the idea isn't ready.

---

## Lessons from This Project

**Content as acquisition, not the tool**
Mikey didn't ask for the digest tool. He asked where I found a specific article. The content was the referral, not the product. This is a pattern worth paying attention to — if the digest is good enough, articles from it will circulate. The implication: quality of curation matters more than features. Each article that travels is a distribution event.

**Real users surface problems solo use hides**
The persona model didn't exist until Mikey showed up. I'd been running a single-user config for months without friction. The moment I needed to onboard someone else, the problem was obvious: asking someone to enumerate keywords is a bad first interaction. Design pressure from a second user revealed a structural gap that solo use had masked indefinitely.

**The onboarding cost is a product problem, not a setup problem**
My first instinct was to ask Mikey "what topics do you care about?" — which frames onboarding as a configuration task. The right frame is: what do I already know about who this person is, and how do I map that to a useful first experience? Personas move onboarding from a setup conversation to a value conversation.

**Over-engineering delivery for user #1**
I almost built email infrastructure (SMTP, app passwords, env vars) before asking what "delivery" actually meant for Mikey. The answer was: a markdown link on WhatsApp. Two minutes of work, not two hours. The lesson is to ask "what does receiving this value look like?" before picking a delivery mechanism.

**Architecture should protect product iteration**
The four-module split is not an engineering cleanliness exercise. It keeps product changes cheap: scraping can run on its own, topic scoring can change without delivering a digest, users can subscribe to global topics without forking the catalog, and feedback can improve ranking without mutating source data. The product benefit is faster iteration on taste without making every run do every expensive step.

**Don't claim what the product doesn't do**
The site subtitle said the digest "learns what matters over time." It doesn't — there's no behavioral learning; the interest profile is explicit. A sharp first user (Mikey is an LLM engineer) notices that kind of gap immediately, and once they catch one inflated claim they discount the rest. What fixed it wasn't softer language — it was finding the thing that *is* true and is actually better: the digest is stateful, it suppresses what it's already shown you, so it gets quieter over time. The honest claim was the stronger claim. I keep relearning that the real differentiator is usually more interesting than the aspirational one.

**The first three lines are the product**
The WhatsApp teaser showed the first three items in file order, which buried a 1,989-point piece at position seven behind a 343-point one. For a glanced notification, those three lines *are* the product — they decide whether the link gets tapped at all. Ordering them by signal cost nothing and changed what the message leads with. The lesson generalizes: wherever attention is rationed (a notification, a subject line, a card), spend the scarce slots on your strongest cards, not whatever the pipeline emitted first.

---

## Questions I'm Sitting With

- If Kintu and Mikey never open the digest, is the problem the content, the delivery, or the habit? How would I know which?
- The `ux_design` persona is thin on HN — design discussions don't trend there. Is HN the right source for a UX practitioner, or should we add Substack feeds specifically for Kintu?
- At what point does "maintain persona keyword sets" become its own ongoing product work? Who decides when `llm_researcher` needs a new keyword because "vibe coding" is a thing now?
