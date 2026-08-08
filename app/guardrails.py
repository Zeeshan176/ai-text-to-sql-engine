import sqlglot
from sqlglot import exp

class SQLGuardrail:
    
    @staticmethod
    def is_safe_query(sql_query: str) -> tuple[bool, str]:
        """Validates that the SQL contains ONLY SELECT statements."""
        try:
            parsed = sqlglot.parse(sql_query)
            for stmt in parsed:
                if not isinstance(stmt, exp.Select):
                    return False, f"Forbidden query type: {type(stmt).__name__.upper()}. Only SELECT queries allowed."
            return True, "Query passed all security AST checks."
        except Exception as e:
            return False, f"SQL Parsing Error: {str(e)}"

    @staticmethod
    def enforce_tenant_isolation(sql_query: str, tenant_id: int) -> str:
        """
        Parses the SQL AST and programmatically injects '{alias}.tenant_id = X'
        to prevent ambiguous column errors during JOINs.
        """
        try:
            expression = sqlglot.parse_one(sql_query)
            
            # Iterate through all SELECT blocks
            for select in expression.find_all(exp.Select):
                from_clause = select.args.get("from")
                if from_clause:
                    # Get the table's alias (e.g., 's') or name (e.g., 'sales')
                    table_alias = from_clause.this.alias_or_name
                    select.where(f"{table_alias}.tenant_id = {tenant_id}", copy=False)
                
            return expression.sql()
        except Exception as e:
            print(f"AST Guardrail Error: {e}")
            return sql_query