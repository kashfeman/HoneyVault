"""Public synthetic presentation fixtures, not document storage or security metadata.

Deliberately contains no decoy classification, sensitivity, or access policy.
Budget and planning examples illustrate convincing business artifacts without
identifying any document as a decoy in employee responses.
"""

DOCUMENTS = (
    dict(id="doc-101", title="Team handbook", category="People", format="TXT",
         owner="Demo People team", updated="2026-11-09", description="Working agreements, meeting etiquette and onboarding essentials.",
         content="TEAM HANDBOOK — FICTIONAL DEMO\n\nWelcome to the sample workspace.\n1. Share a short agenda before team meetings.\n2. Record project decisions in the team notes.\n3. Ask the demo coordinator for onboarding guidance.\n\nThis text is a UI fixture, not company policy."),
    dict(id="doc-102", title="Quarterly budget forecast", category="Finance", format="CSV",
         owner="Demo Finance team", updated="2026-11-08", description="Illustrative departmental allocation and next-quarter planning figures.",
         content="department,quarter,planned_units,allocated_demo_credits\nSample Operations,Q1 2027,12,48000\nSample Research,Q1 2027,8,36000\nSample Services,Q1 2027,10,42000"),
    dict(id="doc-103", title="Product launch roadmap", category="Planning", format="TXT",
         owner="Demo Planning team", updated="2026-11-07", description="Milestones and delivery assumptions for the fictional Aurora initiative.",
         content="AURORA ROADMAP — FICTIONAL DEMO\n\nDecember: prototype review and sample feedback.\nJanuary: evaluate the demonstration workflow.\nFebruary: present the project findings.\n\nDependencies: sample design review and classroom availability.\nNo real product plans are represented."),
    dict(id="doc-104", title="Vendor allocation register", category="Finance", format="CSV",
         owner="Demo Finance team", updated="2026-11-06", description="A sample supplier allocation register for annual planning discussions.",
         content="vendor_reference,service,allocation_demo_credits\nFictional Supplier A,Research materials,12500\nFictional Supplier B,Workshop equipment,8400\nFictional Supplier C,Training resources,6200"),
    dict(id="doc-105", title="Workshop schedule", category="Operations", format="CSV",
         owner="Demo Operations team", updated="2026-11-05", description="Sample workshop dates, rooms and attendance capacities.",
         content="workshop,date,room,capacity\nDemo orientation,2026-11-12,Sample Room A,20\nDemo collaboration,2026-11-15,Sample Room B,16\nDemo project review,2026-11-19,Sample Room A,20"),
    dict(id="doc-106", title="Project brief template", category="Planning", format="TXT",
         owner="Demo Planning team", updated="2026-11-04", description="A reusable outline for goals, deliverables and project review notes.",
         content="PROJECT BRIEF — FICTIONAL DEMO\n\nProject: Sample workspace refresh\nGoal: Demonstrate a clear document discovery experience.\nDeliverables: Library layout, preview page, accessibility review.\nReview: Classroom walkthrough with fictional content only."),
)
CATEGORIES = tuple(sorted({document["category"] for document in DOCUMENTS}))
SORTS = {"newest": "Recently updated", "title": "Title A–Z", "oldest": "Oldest updated"}


def select_documents(query="", category="", sort="newest"):
    """Filter public fixtures without recording queries or altering records."""
    query = query.strip().casefold()
    matches = [document for document in DOCUMENTS
               if (not category or document["category"] == category)
               and query in " ".join(str(document[key]) for key in
                                    ("title", "description", "category", "owner", "format")).casefold()]
    return sorted(matches, key=lambda item: item["title"].casefold() if sort == "title"
                  else item["updated"], reverse=sort == "newest")
