"""The first blog post, seeded once by db_migrate.migrate_blog (insert if the slug is missing).

Plain English, no invented numbers: the one figure quoted is from the WHO falls
fact sheet and is linked. Edit or unpublish it in ops → Blog like any post;
re-running migrations never overwrites it (it only inserts when the slug is gone).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

SAMPLE_SLUG = "caring-for-ageing-parents-in-hyderabad-from-far-away"

SAMPLE_TITLE = "Caring for ageing parents in Hyderabad when you live far away: how KushAlaya helps"

SAMPLE_EXCERPT = (
    "Living in Bengaluru, Dubai or the US while your parents age in Hyderabad? "
    "How a home safety visit and KushLife checks keep you close."
)

SAMPLE_SEO_TITLE = "Elder care in Hyderabad for families far away | KushAlaya"

SAMPLE_TAGS = ["elder care", "hyderabad", "nri families", "home safety", "kushlife"]

SAMPLE_FAQ = [
    {
        "q": "Do I need to be in Hyderabad to book a KushCare Discovery?",
        "a": "No. You fill in the short form from anywhere and we call you back. If a home visit makes sense, "
        "we arrange it with your parents directly and you see everything in the family app.",
    },
    {
        "q": "Is the KushCare Discovery form free?",
        "a": "Yes. Filling in the form and the call back are free, with no obligation to book anything. "
        "The home assessment that follows is free too.",
    },
    {
        "q": "What is KushLife?",
        "a": "KushLife is the short check our caregivers do on every visit: safe, steady, settled and connected. "
        "You get the result after each visit, a weekly summary and a monthly letter for each parent.",
    },
    {
        "q": "Do you only work in Hyderabad?",
        "a": "No. We work with families across India, wherever your parents live. Enter their PIN code on the "
        "[KushCare Discovery](/kushcare-discovery) page and we will call you to arrange the visit.",
    },
    {
        "q": "Will my parents feel watched?",
        "a": "We work with your parents, not around them. Visits are arranged with them, they can say no to "
        "anything, and what they want you to know is part of every KushLife check.",
    },
]

SAMPLE_BODY = """\
If you are reading this from Bengaluru, Pune, Dubai, London or New Jersey, you probably know the feeling. \
Your parents are in Hyderabad, in the home they have lived in for decades. They say they are fine on the \
phone. You want to believe them. And still, every time a call goes unanswered, your mind runs ahead.

This guide is for you: the son, daughter or grandchild who cares deeply but cannot be there every week. \
It explains the real risks of ageing at home, what a good home safety visit looks like, and how KushAlaya \
helps you stay close to your parents' everyday life from wherever you are.

## The challenge when you live far away

Most families we speak to are not looking for a nursing home. Their parents want to stay at home, and \
they want that for them too. The difficulty is knowing what is really going on.

- **You only hear the good news.** Parents do not want to worry you, so a small fall, a missed medicine \
or a bad week often goes unmentioned.
- **Short trips home are busy.** When you do visit, the days fill up with relatives and errands. There is \
rarely time to look at the house with fresh eyes.
- **Help is hard to judge from a distance.** A neighbour, a cook or a driver may be kind and reliable, but \
nobody is checking the whole picture, and nobody is telling you about it in one place.
- **Small changes add up.** A loose rug, a dim corridor, slower steps on the stairs. Each one seems minor \
until they combine on the wrong evening.

None of this means your parents cannot live independently. It means they deserve a plan, and you deserve \
a clear view of how they are doing.

## Home safety risks we see in Hyderabad homes

Falls are the biggest everyday danger for older adults living at home. The World Health Organization \
lists falls as the second leading cause of unintentional injury deaths worldwide \
([WHO fact sheet on falls](https://www.who.int/news-room/fact-sheets/detail/falls)). Many falls happen in \
familiar places, during ordinary routines.

In Hyderabad homes, the things we look at most carefully are:

- **Bathrooms.** Wet floors, a step into the shower area, no grab bar beside the toilet, and a door that \
locks from the inside.
- **Night-time routes.** The walk from bed to bathroom in the dark, often past furniture, wires or a \
threshold.
- **Stairs and entrances.** Uneven steps, a missing handrail, or a gate and staircase that are fine in the \
day but hard to manage after sunset or during the monsoon.
- **Footwear and floors.** Smooth chappals on polished stone or tiles, and loose mats at doorways.
- **Medicines and routine.** Several medicines at different times, kept in different places, managed from \
memory.
- **Getting help quickly.** Whether your parent could call someone if they fell and could not reach a phone.

Every home is different, which is why we start by looking, not by selling.

![A KushAlaya home safety assessor showing an older woman where a grab bar would go in her bathroom](/marketing/blog/assessment.webp)

## What a KushCare Discovery visit includes

[KushCare Discovery](/kushcare-discovery) is where every family starts. You fill in a short form from \
anywhere in the world, telling us about your parent and what worries you. We call you back to understand \
the situation and advise whether a home visit is the right next step. The form and the call are free, \
with no obligation.

If a visit makes sense, one of our trained assessors goes to your parents' home at a time that suits them. \
The approach follows the screening-first idea behind the US CDC's \
[STEADI programme](https://www.cdc.gov/steadi/) for older adult fall prevention. During the visit we:

1. **Talk with your parents first.** How they spend their day, what they find harder than before, and what \
they want to keep doing on their own.
2. **Walk through the home.** Lighting, bathrooms, stairs, floors, the bedroom and the kitchen, room by room.
3. **Look at mobility and daily safety.** How confidently they walk, stand up from a chair and move around \
their own home.
4. **Score the home out of 100.** A simple number you can track as things improve.
5. **Write a prioritised plan.** What to fix first, what can wait, and what it would cost, so you can decide \
together as a family.

You receive the report in the family app, with photos, so you see what the assessor saw.

## KushLife checks on every visit

A one-time assessment is a good start, but ageing is not a one-time event. That is why every visit by a \
KushAlaya caregiver includes a [KushLife](/kushlife) check. "Kush" is the everyday word for comfort and \
contentment, and KushLife is how we measure it. There are four parts:

- **Safe:** hazards, lighting, grab bars and footwear, anything that has raised fall risk since the last visit.
- **Steady:** walking, balance, sit-to-stand and how confidently they move around the house.
- **Settled:** sleep, meals, medicines, mood and routine, the quiet signs that daily life is going well.
- **Connected:** what your parents want you to know, and what you asked us to look at.

![A KushAlaya caregiver checking an older man's blood pressure at his dining table during a visit](/marketing/blog/kushlife-visit.webp)

After each visit you see the four checks and a short note from the caregiver. Every week you get a summary \
of how the visits went, and every month a one-page KushLife letter for each parent. If something needs \
attention straight away, such as a fall, a new symptom or a safety problem, we call you and it shows as an \
alert. It does not wait for the summary.

## The family app: one place for everything

The KushAlaya family app brings it all together, wherever you live:

- **Visits:** what was planned, what happened, and the KushLife result.
- **Reports:** the home assessment, the safety plan and progress as items are fixed.
- **Photos:** the changes made around the home, so you can see the new grab bar or the brighter corridor.
- **Alerts:** anything urgent, with a clear record of who responded and when.
- **Messages:** a direct line to the care team, so questions get answered without a chain of phone calls.

Brothers and sisters in different countries can share the same view, so everyone hears the same thing \
at the same time.

## How to start

You do not need to have everything worked out. Most families begin with one worry: a recent fall, a parent \
living alone, or simply not knowing.

1. **Fill in the [KushCare Discovery form](/kushcare-discovery).** It takes a few minutes on your phone.
2. **Talk to us.** We aim to call you back within 2 hours to understand your parents' situation.
3. **Decide together.** If a home visit helps, we arrange it with your parents. Afterwards, you can choose \
a plan with regular KushLife visits. See [plans and pricing](/packages) for what each one includes.

Your parents have looked after you for a lifetime. Helping them stay safe, steady and independent at home \
is one of the most meaningful things you can do, even from far away. We would be glad to help.
"""


def seed_sample_post(db: Session, tenant_id: int | None = None) -> bool:
    """Insert the sample post for the site tenant when its slug is missing. Returns True if inserted."""
    from app.livewell.blog import clean_markdown, reading_minutes, site_tenant
    from app.models.blog import BlogPost

    if tenant_id is None:
        site = site_tenant(db)
        if site is None:
            return False
        tenant_id = site.id
    exists = db.query(BlogPost.id).filter(BlogPost.tenant_id == tenant_id, BlogPost.slug == SAMPLE_SLUG).first()
    if exists:
        return False
    body = clean_markdown(SAMPLE_BODY)
    db.add(
        BlogPost(
            tenant_id=tenant_id,
            title=SAMPLE_TITLE,
            slug=SAMPLE_SLUG,
            excerpt=SAMPLE_EXCERPT,
            body_md=body,
            cover_image_url="/marketing/blog/cover.webp",
            cover_image_alt="An elderly couple at home in Hyderabad on a video call with their daughter abroad, a caregiver sitting beside them",
            tags=list(SAMPLE_TAGS),
            author_name="KushAlaya care team",
            status="published",
            published_at=datetime.now(timezone.utc),
            seo_title=SAMPLE_SEO_TITLE,
            og_image_url="/marketing/blog/cover-og.jpg",  # same picture as cover.webp; JPG for social previews
            canonical_url="",
            faq=list(SAMPLE_FAQ),
            reading_minutes=reading_minutes(body),
        )
    )
    db.commit()
    return True
