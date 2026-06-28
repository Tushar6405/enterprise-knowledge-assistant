# Engineering Handbook

## Architecture Overview
Our backend is a FastAPI monolith deployed on Render. The frontend is React hosted on Vercel.
We use PostgreSQL (Supabase) as our primary database and ChromaDB for vector search.
All services communicate via REST APIs. We do not use message queues yet.

## Local Development Setup
1. Clone the repository: `git clone https://github.com/yourorg/backend`
2. Copy environment variables: `cp .env.example .env`
3. Fill in secrets from 1Password vault (ask @alice for access)
4. Start all services: `docker-compose up`
5. API runs at http://localhost:8000, docs at http://localhost:8000/docs

## Database Migrations
We use Alembic for migrations. To create a new migration:
```
alembic revision --autogenerate -m "your message"
alembic upgrade head
```
Always test migrations on staging before production. Rollback with `alembic downgrade -1`.

## Code Review Guidelines
- All PRs require at least 1 approval before merging
- PR descriptions must include: what changed, why, and how to test
- Keep PRs under 400 lines where possible — break large features into smaller PRs
- Tag @alice for backend PRs, @bob for infra/DevOps PRs

## Incident Response
- P0 (production down): Page on-call via PagerDuty immediately, create incident channel #inc-YYYYMMDD
- P1 (major feature broken): Notify in #engineering, fix within 4 hours
- Post-mortems are required for all P0 incidents within 48 hours

---

# HR & People Policies

## Hiring Process
1. HR screens resume and schedules intro call
2. Technical round 1: DSA + system design (1 hour)
3. Technical round 2: Take-home assignment (3 days)
4. Culture fit interview with team lead
5. Offer letter sent within 3 working days of final round

## Performance Reviews
Performance reviews happen twice a year: June and December.
Rating scale: Exceeds Expectations / Meets Expectations / Needs Improvement.
Promotions are tied to the December review cycle. Raise percentages: 10-15% for Meets, 20-30% for Exceeds.

## Learning & Development
Each employee gets Rs 10,000/year learning budget. Use it for:
- Online courses (Udemy, Coursera, etc.)
- Books and technical resources
- Conference tickets (with manager approval)
Submit reimbursements via Zoho Expense with receipts.

---

# Product & Process

## Release Process
We release every Friday at 2pm IST. Feature freeze is Thursday 5pm.
Hotfixes can go out any time with CTO approval.
All releases are announced in #releases channel with changelog.

## Customer Support Escalation
- L1: Support team handles basic queries (response within 2 hours)
- L2: Product team investigates feature-related issues (response within 1 business day)
- L3: Engineering team handles bugs and infra issues (response within 4 hours for P1)

## OKR Process
OKRs are set quarterly. All-hands every quarter to review previous OKRs and set new ones.
Individual OKRs must align with team OKRs. Track progress in the shared Notion OKR tracker.
