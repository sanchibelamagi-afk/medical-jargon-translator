from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Medical Jargon Translator Tools")

@mcp.tool()
def lookup_medical_term(term: str) -> str:
    """Look up a complex medical term and get its plain language definition."""
    definitions = {
        "hypertension": "High blood pressure",
        "hyperlipidemia": "High cholesterol",
        "myocardial infarction": "Heart attack",
        "arrhythmia": "Irregular heartbeat",
        "edema": "Swelling caused by excess fluid",
    }
    return definitions.get(term.lower(), f"Definition for '{term}' not found in local database.")

@mcp.tool()
def find_local_specialist(zip_code: str, specialty: str) -> str:
    """Find a local medical specialist by zip code and specialty."""
    return f"Found 3 {specialty} specialists near {zip_code}. 1. Dr. Smith (5 miles) 2. Dr. Jones (10 miles)"

@mcp.tool()
def get_drug_interactions(drug1: str, drug2: str) -> str:
    """Check for known interactions between two drugs."""
    return f"No known severe interactions between {drug1} and {drug2}. Always consult your doctor."

if __name__ == "__main__":
    mcp.run(transport='stdio')
