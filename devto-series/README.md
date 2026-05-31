# Taming Your AI — Dev.to Blog Series

A 7-part blog series for non-technical business owners explaining AI agent governance through relatable analogies (coffee shop, credit card, employee handbook, itemized receipt).

## How to Publish on Dev.to

### Option A: Manual (via Dev.to editor)

1. Go to [dev.to/new](https://dev.to/new)
2. Copy the content of each `.md` file
3. Paste into the editor (Dev.to renders markdown natively)
4. The frontmatter (between `---` lines) will be auto-detected
5. Set **published: true** when ready
6. Submit one post per day for maximum reach

### Option B: Via CLI (using `devto` tool)

```bash
# Install devto CLI
npm install -g @devto/cli

# Set your API key
export DEVTO_API_KEY=your_key_here

# Publish a post
devto publish 01-your-ai-assistant-bought-a-30000-subscription.md
```

## Publishing Order

| Day | File | Title |
|-----|------|-------|
| 1 | `01-your-ai-assistant-bought-a-30000-subscription.md` | Your AI Assistant Just Bought a $30,000 Cloud Subscription |
| 2 | `02-so-what-is-an-ai-agent-anyway.md` | So What IS an AI Agent, Anyway? |
| 3 | `03-giving-your-digital-employee-a-credit-card.md` | Giving Your Digital Employee a Company Credit Card (With Limits) |
| 4 | `04-setting-ground-rules-for-your-digital-employee.md` | Setting Ground Rules for Your Digital Employee |
| 5 | `05-the-receipt-your-ai-didnt-know-it-was-leaving.md` | The Receipt Your AI Didn't Know It Was Leaving |
| 6 | `06-from-panic-to-peace-a-day-in-the-life.md` | From Panic to Peace: A Day in the Life |
| 7 | `07-your-5-minute-action-plan.md` | Your 5-Minute Action Plan |

## Tags Used

Each post uses relevant tags from: `ai`, `agents`, `governance`, `opensource`, `productivity`, `finops`, `beginners`, `explainer`, `security`, `observability`, `monitoring`, `casestudy`, `clinic`, `gettingstarted`, `budgeting`, `devops`

## Frontmatter Fields

Each file includes:
- `title` — SEO-optimized title
- `published: false` — Set to `true` when ready
- `description` — Meta description for search results
- `tags` — Up to 4 comma-separated tags
- `series: "Taming Your AI"` — Groups posts into a series
- `canonical_url` — Optional, points back to your domain
