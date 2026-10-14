
"""Read-only SQL agent for the PMS training database."""

import os
import json

import sqlglot
from sqlglot import exp
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.llm import generate_text


DATABASE_URL = os.getenv("READONLY_DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "READONLY_DATABASE_URL is missing from the .env configuration."
    )

sql_engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"options": "-c statement_timeout=5000"},
)



SQL_SYSTEM_PROMPT = """
You are a PostgreSQL SQL-generation assistant.

Convert the user's question into one SQL query.

Use ONLY these tables and columns:

1. pms_agent_training.tenants
   - tenant_id (text)
   - tenant_name (text)
   - business_type (text)
   - contact_city (text)
   - tenant_status (text)

2. pms_agent_training.leases
   - lease_id (text)
   - tenant_id (text)
   - property_name (text)
   - property_type (text)
   - monthly_rent (numeric)
   - lease_start (date)
   - lease_end (date)
   - lease_status (text)

3. pms_agent_training.rent_bills
   - bill_id (text)
   - lease_id (text)
   - bill_date (date)
   - due_date (date)
   - bill_amount (numeric)

4. pms_agent_training.payments
   - payment_id (text)
   - bill_id (text)
   - payment_date (date)
   - amount_paid (numeric)
   - payment_method (text)
   - payment_status (text)

Rules:
- Always use fully qualified table names.
- Use only the listed columns. Never invent column names.
- Generate exactly one read-only SELECT query.
- Read-only WITH queries are allowed.
- Never generate INSERT, UPDATE, DELETE, DROP, ALTER,
  CREATE, TRUNCATE, or other data-changing statements.
- Never access tables outside pms_agent_training.
- Do not generate multiple statements.
- Return only SQL, without Markdown fences or explanations.
- If the question cannot be answered from these tables,
  return a simple SELECT query that returns no rows.
"""



def generate_sql(question: str) -> str:
    """Generate a SQL query from the user's question."""

    generated_sql = generate_text(
        SQL_SYSTEM_PROMPT,
        question,
    )

    generated_sql = generated_sql.strip()

    if generated_sql.startswith("```"):
        lines = generated_sql.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        generated_sql = "\n".join(lines).strip()

    return generated_sql



ALLOWED_TABLES = {
    "tenants",
    "leases",
    "rent_bills",
    "payments",
}

ALLOWED_SCHEMA = "pms_agent_training"


def validate_sql(query: str) -> str:
    """Allow only a single read-only SELECT query on approved tables."""

    statements = sqlglot.parse(query, read="postgres")

    # Reject empty SQL or multiple statements.
    if len(statements) != 1 or statements[0] is None:
        raise ValueError("Only one SQL query is allowed.")

    tree = statements[0]

    if not isinstance(tree, exp.Select):
        raise ValueError("Only SELECT queries are allowed.")

    if tree.args.get("into") is not None:
        raise ValueError("SELECT INTO is not allowed.")

    for table in tree.find_all(exp.Table):
        table_name = table.name.lower()
        schema_name = (table.db or "").lower()

        if table_name not in ALLOWED_TABLES:
            raise ValueError(
                f"Table '{table_name}' is not allowed."
            )

        if schema_name != ALLOWED_SCHEMA:
            raise ValueError(
                "Every table must explicitly use the "
                "pms_agent_training schema."
            )

    return tree.sql(dialect="postgres")



def execute_sql(question: str) -> tuple[str, list[dict]]:
    """Generate, validate, and execute a read-only SQL query."""

    generated_query = generate_sql(question)

    safe_query = validate_sql(generated_query)

    limited_query = (
        f"SELECT * FROM ({safe_query}) AS agent_results LIMIT 50"
    )

   
    try:
        with sql_engine.connect() as connection:
            result = connection.execute(text(limited_query))

            rows = [
                dict(row)
                for row in result.mappings().fetchmany(50)
            ]

    except SQLAlchemyError as exc:
        raise RuntimeError(
            "The generated SQL could not be executed. "
            "Check the database schema and column names."
        ) from exc

    return safe_query, rows



def answer_sql_question(question: str) -> tuple[str, str]:
    """Answer a database question using validated SQL results."""

    safe_query, rows = execute_sql(question)

    rows_json = json.dumps(rows, default=str)

    system_prompt = """
    You answer questions using database query results.

    Rules:
    - Use only the supplied database results.
    - Do not invent facts or numbers.
    - Explain the results in simple, clear language.
    - If no rows are returned, say no matching records were found.
    - Do not claim that an operation was performed.
    """

    user_prompt = (
        f"User question:\n{question}\n\n"
        f"Database results:\n{rows_json}"
    )

    answer = generate_text(system_prompt, user_prompt)

    return answer, safe_query




