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

---

## Questions I'm Sitting With

- If Kintu and Mikey never open the digest, is the problem the content, the delivery, or the habit? How would I know which?
- The `ux_design` persona is thin on HN — design discussions don't trend there. Is HN the right source for a UX practitioner, or should we add Substack feeds specifically for Kintu?
- At what point does "maintain persona keyword sets" become its own ongoing product work? Who decides when `llm_researcher` needs a new keyword because "vibe coding" is a thing now?
