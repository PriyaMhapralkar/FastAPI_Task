
"""Choose the data source for a user's question."""

from app.llm import generate_text



ROUTING_SYSTEM_PROMPT = """
You are a question-routing classifier.

Choose exactly one category:
- documents: The question can be answered using uploaded documents only.
- database: The question can be answered using the PMS training database only.
- both: The question requires information from BOTH uploaded documents
  and the PMS training database.

Important rules:
1. If the question asks about uploaded document content AND tenant,
   lease, rent, bill, payment, or database information, choose both.
2. If the question asks about Spring MVC, Java concepts, or other
   technical explanations based on uploaded documents, choose documents
   unless it also asks for database information.
3. If the question asks for tenant counts, rent amounts, lease status,
   payment status, or other PMS records only, choose database.
4. Choose both whenever the question explicitly requests information
   from both sources.

Examples:
Question: Explain Spring MVC based on uploaded documents.
Answer: documents

Question: How many tenants are in the database?
Answer: database

Question: Explain Spring MVC and tell me how many tenants are in the database.
Answer: both

Return exactly one lowercase word:
documents
database
or both

Do not answer the user's question.
Do not include explanations or punctuation.
"""



def route_question(question: str) -> str:
    """Classify a question into documents, database, or both."""

    result = generate_text(
        ROUTING_SYSTEM_PROMPT,
        question,
    ).strip().lower()

    for route in ("documents", "database", "both"):
        if result == route:
            return route

    return "documents"
