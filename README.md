<a name="readme-top"></a>

<p align="center">
  <a href="https://github.com/mindsdb/mindsdb">
    <img src="/assets/mindsdb-header-github.png" alt="Query engine for AI analytics, powering agents to answer questions across all your live data" width="100%" />
  </a>
</p>

<div align="center">
  <a href="https://pypi.org/project/MindsDB/" target="_blank">
    <img src="https://badge.fury.io/py/MindsDB.svg" alt="MindsDB Release" />
  </a>
  <a href="https://www.python.org/downloads/" target="_blank">
    <img src="https://img.shields.io/badge/python-3.10.x%7C%203.11.x%7C%203.12.x%7C%203.13.x-brightgreen.svg" alt="Python supported" />
  </a>
  <a href="https://hub.docker.com/r/mindsdb/mindsdb" target="_blank">
  <img src="https://img.shields.io/docker/pulls/mindsdb/mindsdb.svg?logo=docker&label=Docker%20pulls&cacheSeconds=86400" alt="Docker pulls" />
  </a>

  <p align="center">
	<a href="https://github.com/mindsdb/anton">AI-coworker</a>
    ·
    <a href="https://mindsdb.com?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Website</a>
    ·
    <a href="https://docs.mindsdb.com?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Docs</a>
    ·
    <a href="https://mindsdb.com/contact?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Contact us for a demo</a>
    ·
    <a href="https://mindsdb.com/joincommunity?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Community Slack</a>
  </p>
</div>

---

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/mindsdb/mindsdb)

MindsDB develops the following products:

* [ANTON](https://github.com/mindsdb/anton) - A personal AI agent that helps you get work done. Tell it what you need in plain language and it takes it from there - sending emails, calling APIs, connecting to data sources, building dashboards, and delivering results. No setup, no plugins, no fuss.

* [Query Engine](https://docs.mindsdb.com) - The product you are looking at, is a popular query engine for semantic-search.


## What you can build with MindsDB Products

| CONVERSATIONAL ANALYTICS AGENTS | SEMANTIC SEARCH AGENTS |
| --- | --- |
| Get precise, data-driven answers using natural language. <br /><br /> Unify and query data across sources (MySQL, Salesforce, Shopify, etc.), without ETL. <br /><br /> <a href="https://github.com/mindsdb/anton">Try Anton</a> | Ground LLM responses in your most relevant internal knowledge. <br /><br /> Search across unstructured sources like documents, support tickets, Google Drive, and more. <br /><br /> <a href="https://www.youtube.com/watch?v=HN4fHtS4mvo">Watch video</a> |

## How MindsDB - Query Engine works
<div align="center">
  <a href="https://www.youtube.com/watch?v=HN4fHtS4mvo" title="Watch demo">
    <img
      src="/assets/mindsdb_demo.gif"
      alt="MindsDB demo - answer questions in plain English from live enterprise data"
      title="Click to watch the full video"
      width="80%"
    />
  </a>
</div>

MindsDB - Query Engine follows a simple workflow: **Connect → Unify → Respond**. At the center is an SQL-compatible data language with additional constructs for searching unstructured data, managing workflows (jobs/triggers), and building agents.

<table style="width:100%; border-collapse:collapse; border:none;">
  <tr>
    <td style="width:25%; border:none; padding:8px 16px; vertical-align:middle;">
      <strong><a href="https://docs.mindsdb.com/integrations/data-overview?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Connect</a></strong>
    </td>
    <td style="width:75%; border:none; padding:8px 16px; vertical-align:middle;">
      <strong>Universal data access:</strong> Give your agents federated access to 200+ live data sources (Postgres, MongoDB, Slack, files, and more).
    </td>
  </tr>
  <tr>
    <td style="width:25%; border:none; padding:8px 16px; vertical-align:middle;">
      <strong><a href="https://docs.mindsdb.com/mindsdb-unify?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Unify</a></strong>
    </td>
    <td style="width:75%; border:none; padding:8px 16px; vertical-align:middle;">
      <strong>Dynamic context engine:</strong> Fuse structured tables with vectorized data (text, PDFs, HTML) inside a Knowledge Base.
    </td>
  </tr>
  <tr>
    <td style="width:25%; border:none; padding:8px 16px; vertical-align:middle;">
      <strong><a href="https://docs.mindsdb.com/mindsdb-respond?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Respond</a></strong>
    </td>
    <td style="width:75%; border:none; padding:8px 16px; vertical-align:middle;">
      <strong>Autonomous reasoning:</strong> Deploy agents that blend and retrieve data points across your stack to produce grounded answers.
    </td>
  </tr>
</table>

## Setup

Users can install MindsDB via <a href="https://docs.mindsdb.com/setup/self-hosted/docker?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Docker</a>, <a href="https://docs.mindsdb.com/setup/self-hosted/docker-desktop?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Docker Extension</a>, or <a href="https://docs.mindsdb.com/contribute/install?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">PyPI</a>.

Here is how to pull and run MindsDB via Docker:
```bash
docker run --name mindsdb_container \
-e MINDSDB_APIS=http,mysql \
-p 47334:47334 -p 47335:47335 \
mindsdb/mindsdb:latest
```

## Usage

**Follow the <a href="https://docs.mindsdb.com/quickstart-tutorial?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">quickstart guide</a> to get started with MindsDB using our demo data.**

Retrieve and analyze data from over 200 <a href="https://docs.mindsdb.com/integrations/data-overview?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">data sources</a> in one SQL dialect. For AI agents, this means faster response time, better accuracy, and lower token consumption.
```sql
--use SQL to aggregate pipeline data from Salesforce 
SELECT SUM(ExpectedRevenue) AS open_pipeline
FROM salesforce.opportunities
WHERE close_date >= CURDATE()

--use the same dialect to retrieve even from a non-SQL database, like MongoDB
SELECT COUNT(*) AS negative_emails_last_30_days
FROM mongodb.support_tickets
WHERE sentiment = 'negative'
  AND created_at >= CURRENT_DATE - INTERVAL '30 days';
```

Create <a href="https://docs.mindsdb.com/mindsdb_sql/sql/create/view?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">views</a> and join data even from different types of data systems.
```sql
--join MongoDB and Salesforce data
CREATE VIEW risky_renewals AS (
SELECT *
FROM mongodb.support_tickets AS reviews
JOIN salesforce.opportunities AS deals
  ON reviews.customer_domain = deals.customer_domain
WHERE deals.type = "renewal"
  AND reviews.sentiment = "negative"
);
```

Join vectorized and structured data inside a <a href="https://docs.mindsdb.com/mindsdb_sql/knowledge_bases/overview?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">knowledge base</a>. Combine semantic search with precise metadata criteria in a single SQL query.
```sql
--create a knowledge base for customer issues 
CREATE KNOWLEDGE_BASE customers_issues
USING
  storage = my_vector.db,
  content_columns = ['ticket_description'],
  metadata_columns = ['customer_name', 'segment', 'revenue', 'is_pending_renewal'];

--find large customers who submitted ticket related to data security topics  
SELECT * FROM customers_issues
WHERE content = 'data security'
AND
  is_pending_renewal = 'true'
AND
  revenue > 1000000;
```

Use MindsDB pre-packaged <a href="https://docs.mindsdb.com/mindsdb_sql/agents/agent_syntax?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">data agents</a> and connect them with your own. See how to use MindsDB via <a href="https://docs.mindsdb.com/overview_sdks_apis?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">API or MCP</a>.
```sql
CREATE AGENT my_agent
USING
    model = {
        "provider": "openai",
        "model_name" : "gpt-xx",
        "api_key": "sk-..."
    },
    data = {
         "knowledge_bases": ["mindsdb.customer_issues"],
         "tables": ["salesforce.opportunities", "postgres.sales", "mongodb.support_tickets"]
    },
    prompt_template = 'my prompt template and agent guidance';
```
See MindsDB’s recommended usage of agents <a href="https://docs.mindsdb.com/mindsdb_sql/agents/agent?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">here</a> and how to automate workflows with <a href="https://docs.mindsdb.com/mindsdb_sql/sql/create/jobs?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">jobs</a>.

## 📃 Tutorials
- Enterprise Knowledge Search (<a href="https://mindsdb.com/blog/fast-track-knowledge-bases-how-to-build-semantic-ai-search-by-andriy-burkov?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- Advanced Semantic Search  (<a href="https://mindsdb.com/blog/blend-hybrid-retrieval-with-structured-data-using-mindsdb-knowledge-bases?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- Customer Support Automation (<a href="https://mindsdb.com/blog/building-janus-an-ai-powered-customer-support-helpdesk-system-powered-by-mindsdb?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example1</a>, <a href="https://mindsdb.com/blog/building-agentic-workflow-auto-banking-customer-service-with-mindsdb?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example2</a>)
- Intelligent Content Discovery (<a href="https://mindsdb.com/blog/mysql-mindsdb-unlocks-intelligent-content-discovery-for-web-cms-with-knowledge-bases-and-cursor?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- Financial Analysis Agents (<a href="https://mindsdb.com/blog/streamline-financial-analysis-with-mindsdb-s-knowledge-bases-and-hybrid-search?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- Real-time AI-powered analytics (<a href="https://mindsdb.com/blog/mariadb-mindsdb-turns-woocommerce-data-to-insights-with-real-time-ai-analytics-for-ecommerce-teams?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- Conversational Data Assistants (<a href="https://mindsdb.com/blog/unlocking-operational-intelligence-in-energy-utilities-with-mindsdb-knowledge-bases-hybrid-search?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- CRM Intelligence (<a href="https://mindsdb.com/blog/unlocking-salesforce-crm-intelligence-with-mindsdb-s-ai-powered-knowledge-bases?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- Compliance & Customer Intelligence (<a href="https://mindsdb.com/blog/enterprise-software-vendors-drive-compliance-customer-insights-with-mindsdb-knowledge-bases-hybrid-search?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
- Conversation Intelligence (<a href="https://mindsdb.com/blog/introducing-mindsdb-s-integration-with-gong-ai-analytics-on-call-data?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">example</a>)
Subscribe to our (<a href="https://mindsdb.com/blog?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">blog</a>) for more

## 🫴 Help and support

Stuck on a query? Found a bug? We’re here to help.
<table style="width:100%; border-collapse:collapse;">
  <tr>
    <td style="width:30%; border:1px solid #d0d7de; padding:12px; vertical-align:top;">
      Ask a question
    </td>
    <td style="width:70%; border:1px solid #d0d7de; padding:12px; vertical-align:top;">
      Join our <a href="https://mindsdb.com/joincommunity">Slack Community</a>.
    </td>
  </tr>
  <tr>
    <td style="width:30%; border:1px solid #d0d7de; padding:12px; vertical-align:top;">
      Report a bug
    </td>
    <td style="width:70%; border:1px solid #d0d7de; padding:12px; vertical-align:top;">
      Open a <a href="https://github.com/mindsdb/mindsdb/issues">GitHub Issue</a>. Please include reproduction steps!
    </td>
  </tr>
  <tr>
    <td style="width:30%; border:1px solid #d0d7de; padding:12px; vertical-align:top;">
      Get commercial support
    </td>
    <td style="width:70%; border:1px solid #d0d7de; padding:12px; vertical-align:top;">
      Contact the <a href="https://mindsdb.com/contact?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">MindsDB Team</a> for enterprise SLAs and custom solutions.
    </td>
  </tr>
</table>

**Security Note:** If you find a security vulnerability, please do not open a public issue. Refer to our <a href="https://github.com/mindsdb/mindsdb/security">security policy</a> for reporting instructions.

## 🤝 Contribute to MindsDB

MindsDB is open source and contributions are welcome! You can submit code changes through pull requests or by opening issues to report bugs, suggest new features, or enhancements.

**Ways you can help:**
- Develop a <a href="https://docs.mindsdb.com/contribute/data-handlers">database integration</a>
- Develop an <a href="https://docs.mindsdb.com/contribute/app-handlers">app integration</a>
- Identify and fix bugs

**How to contribute**

- Read the <a href="https://docs.mindsdb.com/contribute/contribute?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">contribution guide</a> to get set up.
- Browse <a href="https://github.com/mindsdb/mindsdb/issues">open issues</a>.
- Join the #contributors channel in <a href="https://mindsdb.com/joincommunity">Slack</a>.
- Explore <a href="https://mindsdb.com/community?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">community rewards and programs</a>.

<div align="center">

<strong>Our top 100 contributors</strong>

<a href="https://github.com/mindsdb/mindsdb/graphs/contributors">
<img src="https://contrib.rocks/image?repo=mindsdb/mindsdb&max=100&columns=10" />
</a>
	
Made with [contrib.rocks](https://contrib.rocks)
</div>

## 📚 Resources
- <a href="https://docs.mindsdb.com?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Documentation</a>
- <a href="https://mindsdb.com/blog?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Blog</a>
- <a href="https://mindsdb.com/events?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Events</a>
- <a href="https://mindsdb.com/joincommunity">Community Slack</a>
- <a href="https://mindsdb.com/press-kit?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Brand guidelines</a>
- <a href="https://mindsdb.com/contact?utm_medium=community&utm_source=github&utm_campaign=mindsdb%20repo">Contact form</a>
